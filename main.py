import dspy

from settings import settings
from irene.dspy_modules import CodeSummary

def main():
    lm = dspy.LM(
        model=settings.model,
        api_base=settings.api_base,
        temperature=settings.temperature,
        api_key=settings.api_key,
    )
    dspy.configure(lm=lm)

    summarise = dspy.ChainOfThought(CodeSummary)
    res = summarise(c_code="""
#include <math.h>

double newton(double (*f)(double), double (*df)(double),
    double x0, int max_iter, double tol) {
    for (int i = 0; i < max_iter; i++) {
        double fx = f(x0);
        double dfx = df(x0);
        if (fabs(dfx) < 1e-14) {
            /* derivative too small */
            break;
        }
        double x1 = x0 - fx / dfx;
        if (fabs(x1 - x0) < tol)
            return x1;
        x0 = x1;
    }
    return x0;
}""")
    print(res)

if __name__ == "__main__":
    main()
