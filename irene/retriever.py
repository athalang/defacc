import json
from dataclasses import dataclass
from typing import List, Dict
from pathlib import Path
from rank_bm25 import BM25Okapi

@dataclass
class TranslationExample:
    c_code: str
    rust_code: str
    categories: List[str]  # ["I/O", "Array", etc.]
    description: str

class ExampleRetriever:
    def __init__(self, corpus_path: str = "irene/corpus/examples.json"):
        self.corpus_path = Path(corpus_path)
        self.examples: List[TranslationExample] = []
        self.bm25: Dict[str, BM25Okapi] = {}  # category -> BM25 index
        self._load_corpus()

    def _load_corpus(self):
        if not self.corpus_path.exists():
            print(f"Warning: Corpus file {self.corpus_path} not found. Using empty corpus.")
            return

        with open(self.corpus_path, "r") as f:
            data = json.load(f)

        for item in data:
            self.examples.append(
                TranslationExample(
                    c_code=item["c_code"],
                    rust_code=item["rust_code"],
                    categories=item["categories"],
                    description=item["description"],
                )
            )

        self._build_indices()

    def _build_indices(self):
        category_examples = {}
        for example in self.examples:
            for cat in example.categories:
                if cat not in category_examples:
                    category_examples[cat] = []
                category_examples[cat].append(example)

        # Build BM25 index for each category
        for cat, examples in category_examples.items():
            tokenized_corpus = [ex.c_code.split() for ex in examples]
            self.bm25[cat] = BM25Okapi(tokenized_corpus)

    def retrieve(self, c_code: str, categories: List[str], top_k: int = 3) -> List[TranslationExample]:
        if not categories or not self.examples:
            return []

        # Get examples from relevant categories
        relevant_examples = []
        for example in self.examples:
            if any(cat in example.categories for cat in categories):
                relevant_examples.append(example)

        if not relevant_examples:
            return []

        # Use BM25 to rank examples
        # For simplicity, we'll use the first matching category's index
        matching_cat = None
        for cat in categories:
            if cat in self.bm25:
                matching_cat = cat
                break

        if not matching_cat:
            # No BM25 index, return first top_k examples
            return relevant_examples[:top_k]

        # Score with BM25
        tokenized_query = c_code.split()
        scores = self.bm25[matching_cat].get_scores(tokenized_query)

        # Get examples for this category
        cat_examples = [ex for ex in self.examples if matching_cat in ex.categories]

        # Sort by score and return top-k
        scored_examples = list(zip(scores, cat_examples))
        scored_examples.sort(key=lambda x: x[0], reverse=True)

        return [ex for _, ex in scored_examples[:top_k]]


def format_examples(examples: List[TranslationExample]) -> str:
    """Format retrieved examples for the LLM."""
    if not examples:
        return "No similar examples found."

    formatted = "Similar translation examples:\n\n"
    for i, ex in enumerate(examples, 1):
        formatted += f"Example {i}: {ex.description}\n"
        formatted += f"C code:\n```c\n{ex.c_code}\n```\n\n"
        formatted += f"Rust code:\n```rust\n{ex.rust_code}\n```\n\n"

    return formatted
