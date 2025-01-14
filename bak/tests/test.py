def ttt(t):
    print("ttt", t)


def loopz(t):
    try:
        match t:
            case 1:
                print(11111)
                return

            case 2:
                print(22222)

            case 3:
                print(33333)
                return ttt(3)

            case _:
                print("------")
                raise Exception("______")

    finally:
        print("toch ook nog", t)


if __name__ == "__main__":
    loopz(1)
    loopz(2)
    loopz(3)
    loopz(0)