import json
from dataclasses import dataclass
from typing import Dict, List, Optional
from pathlib import Path
from rank_bm25 import BM25Okapi

@dataclass
class TranslationExample:
    c_code: str
    rust_code: str
    categories: List[str]  # ["I/O", "Array", etc.]
    description: str

class ExampleRetriever:
    def __init__(self, corpus_path: str = "guardian/corpus/examples.json"):
        self.corpus_path = Path(corpus_path)
        self.examples: List[TranslationExample] = []
        self.examples_by_category: Dict[str, List[TranslationExample]] = {}
        self.bm25: Dict[str, BM25Okapi] = {}  # category -> BM25 index
        self._load_corpus()

    def _load_corpus(self):
        if not self.corpus_path.exists():
            print(f"Warning: Corpus file {self.corpus_path} not found. Using empty corpus.")
            return

        with open(self.corpus_path, "r") as f:
            data = json.load(f)

        for item in data:
            example = TranslationExample(
                c_code=item["c_code"],
                rust_code=item["rust_code"],
                categories=item["categories"],
                description=item["description"],
            )
            self.examples.append(example)
            for cat in example.categories:
                self.examples_by_category.setdefault(cat, []).append(example)

    def _tokenize(self, text: str) -> List[str]:
        return text.split()

    def _get_index(self, category: str) -> Optional[BM25Okapi]:
        if category in self.bm25:
            return self.bm25[category]
        examples = self.examples_by_category.get(category)
        if not examples:
            return None
        tokenized_corpus = [self._tokenize(ex.c_code) for ex in examples]
        index = BM25Okapi(tokenized_corpus)
        self.bm25[category] = index
        return index

    def retrieve(self, c_code: str, categories: List[str], top_k: int = 3) -> List[TranslationExample]:
        if not categories or not self.examples:
            return []

        scored: Dict[int, List] = {}
        fallback: List[TranslationExample] = []
        tokenized_query = self._tokenize(c_code)

        for category in categories:
            examples = self.examples_by_category.get(category)
            if not examples:
                continue
            fallback.extend(examples)
            index = self._get_index(category)
            if not index:
                continue
            scores = index.get_scores(tokenized_query)
            for example, score in zip(examples, scores):
                key = id(example)
                current = scored.get(key)
                if current is None or score > current[0]:
                    scored[key] = [score, example]

        if scored:
            ordered = sorted(scored.values(), key=lambda item: item[0], reverse=True)
            return [example for _, example in ordered[:top_k]]

        if fallback:
            seen = set()
            deduped: List[TranslationExample] = []
            for example in fallback:
                key = id(example)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(example)
            return deduped[:top_k]

        return []


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
