from constants import TIMESLOT_LENGTH
from models import Header, Extrinsic, Block


def main():
    header = Header()
    extrinsic = Extrinsic()
    block = Block(header, extrinsic)
    print(f'Timeslot {TIMESLOT_LENGTH}')


if __name__ == '__main__':
    main()
