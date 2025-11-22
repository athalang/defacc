"""Test cases from the IRENE paper examples."""

# Test case 1: scanf with two integers
TEST_SCANF_TWO_INTS = """
#include <stdio.h>

int main() {
    int a, b;
    scanf("%d%d", &a, &b);
    printf("%d\\n", a + b);
    return 0;
}
"""

# Test case 2: Array indexing with int
TEST_ARRAY_INDEXING = """
#include <stdio.h>

int main() {
    int arr[10];
    for (int i = 0; i < 10; i++) {
        arr[i] = i * 2;
    }

    int idx = 5;
    printf("%d\\n", arr[idx]);
    return 0;
}
"""

# Test case 3: long long cast for multiplication
TEST_LONG_LONG_MULT = """
#include <stdio.h>

int main() {
    int x = 100000;
    int y = 100000;
    long long result = (long long)x * y;
    printf("%lld\\n", result);
    return 0;
}
"""

# Test case 4: malloc with sizeof
TEST_MALLOC_ARRAY = """
#include <stdio.h>
#include <stdlib.h>

int main() {
    int n = 10;
    int *arr = (int*)malloc(n * sizeof(int));

    for (int i = 0; i < n; i++) {
        arr[i] = i * i;
    }

    printf("%d\\n", arr[5]);
    free(arr);
    return 0;
}
"""

# Test case 5: Mixed scanf and array operations
TEST_MIXED_IO_ARRAY = """
#include <stdio.h>

int main() {
    int n;
    scanf("%d", &n);

    int arr[100];
    for (int i = 0; i < n; i++) {
        scanf("%d", &arr[i]);
    }

    int sum = 0;
    for (int i = 0; i < n; i++) {
        sum += arr[i];
    }

    printf("%d\\n", sum);
    return 0;
}
"""

# Test case 6: Simple pointer allocation
TEST_SIMPLE_POINTER = """
#include <stdlib.h>

int main() {
    int *p = (int*)malloc(sizeof(int));
    *p = 42;
    int value = *p;
    free(p);
    return 0;
}
"""

# Test case 7: Float conversion
TEST_FLOAT_CONVERSION = """
#include <stdio.h>

int main() {
    int x = 10;
    int y = 3;
    float result = (float)x / y;
    printf("%.2f\\n", result);
    return 0;
}
"""

# All test cases
ALL_TEST_CASES = {
    "scanf_two_ints": TEST_SCANF_TWO_INTS,
    "array_indexing": TEST_ARRAY_INDEXING,
    "long_long_mult": TEST_LONG_LONG_MULT,
    "malloc_array": TEST_MALLOC_ARRAY,
    "mixed_io_array": TEST_MIXED_IO_ARRAY,
    "simple_pointer": TEST_SIMPLE_POINTER,
    "float_conversion": TEST_FLOAT_CONVERSION,
}
