from constants import TIMESLOT_LENGTH
from models import Extrinsic, Block
from models.header import Header


def main():
    header = Header()
    extrinsic = Extrinsic()
    block = Block(header, extrinsic)
    print(f'Timeslot {TIMESLOT_LENGTH}')


if __name__ == '__main__':
    main()
