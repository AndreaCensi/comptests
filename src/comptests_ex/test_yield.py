
def check_it(n):
    print(n)

def test_yielding():
    for n in [0,1,2]:
        yield check_it, n