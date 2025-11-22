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

# ===== ADVERSARIAL TEST CASES =====
# These test cases demonstrate common security vulnerabilities
# IRENE should prevent these from becoming unsafe Rust code

# Test case 8: Buffer overflow risk via strcpy
TEST_BUFFER_OVERFLOW = """
#include <stdio.h>
#include <string.h>

int main() {
    char buffer[10];
    char *input = "This is a very long string that exceeds buffer size";
    strcpy(buffer, input);  // Dangerous! Buffer overflow
    printf("%s\\n", buffer);
    return 0;
}
"""

# Test case 9: Integer overflow
TEST_INTEGER_OVERFLOW = """
#include <stdio.h>
#include <limits.h>

int main() {
    int a = INT_MAX;
    int b = a + 1;  // Overflow! Wraps to negative
    printf("Result: %d\\n", b);
    return 0;
}
"""

# Test case 10: Use after free
TEST_USE_AFTER_FREE = """
#include <stdlib.h>
#include <stdio.h>

int main() {
    int *ptr = (int*)malloc(sizeof(int));
    *ptr = 42;
    free(ptr);
    int value = *ptr;  // Use after free! Undefined behavior
    printf("%d\\n", value);
    return 0;
}
"""

# Test case 11: Double free
TEST_DOUBLE_FREE = """
#include <stdlib.h>

int main() {
    int *ptr = (int*)malloc(sizeof(int));
    *ptr = 100;
    free(ptr);
    free(ptr);  // Double free! Undefined behavior
    return 0;
}
"""

# Test case 12: Array bounds violation
TEST_ARRAY_BOUNDS = """
#include <stdio.h>

int main() {
    int arr[5] = {1, 2, 3, 4, 5};
    int idx = 10;  // Out of bounds!
    printf("%d\\n", arr[idx]);  // Accessing invalid memory
    return 0;
}
"""

# Test case 13: Uninitialized memory read
TEST_UNINITIALIZED_READ = """
#include <stdio.h>

int main() {
    int x;  // Uninitialized
    printf("%d\\n", x);  // Reading uninitialized memory
    return 0;
}
"""

# Test case 14: Format string vulnerability
TEST_FORMAT_STRING = """
#include <stdio.h>

int main() {
    char user_input[100] = "%s%s%s%s";
    printf(user_input);  // Format string vulnerability
    return 0;
}
"""

# Test case 15: NULL pointer dereference
TEST_NULL_DEREF = """
#include <stdio.h>
#include <stdlib.h>

int main() {
    int *ptr = NULL;
    *ptr = 42;  // NULL pointer dereference
    return 0;
}
"""

# All test cases (basic + adversarial)
ALL_TEST_CASES = {
    # Basic test cases
    "scanf_two_ints": TEST_SCANF_TWO_INTS,
    "array_indexing": TEST_ARRAY_INDEXING,
    "long_long_mult": TEST_LONG_LONG_MULT,
    "malloc_array": TEST_MALLOC_ARRAY,
    "mixed_io_array": TEST_MIXED_IO_ARRAY,
    "simple_pointer": TEST_SIMPLE_POINTER,
    "float_conversion": TEST_FLOAT_CONVERSION,

    # Adversarial test cases (security vulnerabilities)
    "buffer_overflow": TEST_BUFFER_OVERFLOW,
    "integer_overflow": TEST_INTEGER_OVERFLOW,
    "use_after_free": TEST_USE_AFTER_FREE,
    "double_free": TEST_DOUBLE_FREE,
    "array_bounds": TEST_ARRAY_BOUNDS,
    "uninitialized_read": TEST_UNINITIALIZED_READ,
    "format_string": TEST_FORMAT_STRING,
    "null_deref": TEST_NULL_DEREF,
}

# Categorize test cases for targeted evaluation
BASIC_TEST_CASES = {
    "scanf_two_ints": TEST_SCANF_TWO_INTS,
    "array_indexing": TEST_ARRAY_INDEXING,
    "long_long_mult": TEST_LONG_LONG_MULT,
    "malloc_array": TEST_MALLOC_ARRAY,
    "mixed_io_array": TEST_MIXED_IO_ARRAY,
    "simple_pointer": TEST_SIMPLE_POINTER,
    "float_conversion": TEST_FLOAT_CONVERSION,
}

ADVERSARIAL_TEST_CASES = {
    "buffer_overflow": TEST_BUFFER_OVERFLOW,
    "integer_overflow": TEST_INTEGER_OVERFLOW,
    "use_after_free": TEST_USE_AFTER_FREE,
    "double_free": TEST_DOUBLE_FREE,
    "array_bounds": TEST_ARRAY_BOUNDS,
    "uninitialized_read": TEST_UNINITIALIZED_READ,
    "format_string": TEST_FORMAT_STRING,
    "null_deref": TEST_NULL_DEREF,
}
