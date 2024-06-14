class State:
    #graypaper-equation: 15
    #graypaper-reference: ALPHA
    def __init__(self):
        # GENERAL THOUGHT: I DO NOT THINK WE ARE GOING TO NEED THE STATE OBJECT ITSELF SINCE WERE ARE SILOING ALL INTERACTION WITH STATE PER State subclass, e.g. StateTimeslot (state_timeslot.py)
        self = {}
