import json
import os
import unittest
from dataclasses import dataclass
from os import path
from typing import Optional

from parameterized import parameterized

from pyjamaz.mixins import SerializableMixin
from pyjamaz.types.safrole import CustomErrorCode, TicketBody, SlotSealerSeries, ValidatorData, TicketEnvelope, \
    EpochMark, OutputMarks, State, Input, Output
from scalecodec.base import ScaleBytes


@dataclass
class Testcase(SerializableMixin):
    input: Input  # Input.
    pre_state: State  # Pre-execution state.
    output: Output  # Output.
    post_state: State  # Post-execution state.


class TestSerializableMixin(unittest.TestCase):

    def setUp(self):
        data = {
            'bandersnatch': '0x5e465beb01dbafe160ce8216047f2155dd0569f058afd52dcea601025a8d161d',
            'ed25519': '0x3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29',
            'bls': '0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
            'metadata': '0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        }

        self.test_obj = ValidatorData.deserialize(data)

    def test_dataclass_serialization(self):
        output = Output(ok=OutputMarks(epoch_mark=None, tickets_mark=None))
        value = output.serialize()
        self.assertEqual({'ok': {'epoch_mark': None, 'tickets_mark': None}}, value)

        output = Output(err=CustomErrorCode.duplicate_ticket)
        value = output.serialize()

        self.assertEqual({'err': 'duplicate_ticket'}, value)

    def test_dataclass_to_scale_type(self):
        output = Output(
            ok=OutputMarks(
                epoch_mark=EpochMark(
                    entropy=bytes(32),
                    validators=[bytes(32), bytes(32), bytes(32), bytes(32), bytes(32), bytes(32)]
                ),
                tickets_mark=None
            )
        )
        scale_type = output.to_scale_type()
        output2 = Output.from_scale_type(scale_type)
        self.assertEqual(output, output2)

    def test_deserialize(self):

        data = {
            'bandersnatch': '0x5e465beb01dbafe160ce8216047f2155dd0569f058afd52dcea601025a8d161d',
            'ed25519': '0x3b6a27bcceb6a42d62a3a8d02a6f0d73653215771de243a63ac048a18b59da29',
            'bls': '0x000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
            'metadata': '0x0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        }

        validator_obj = ValidatorData.deserialize(data)

        self.assertEqual(self.test_obj, validator_obj)
        self.assertEqual(data, validator_obj.serialize())

    def test_from_to_scale_bytes(self):

        scale_data = self.test_obj.to_scale_bytes()

        validator_obj = ValidatorData.from_scale_bytes(scale_data)

        self.assertEqual(self.test_obj, validator_obj)


# JSON conversion functions

def hex_to_bytes(hex_str: str) -> bytes:
    return bytes.fromhex(hex_str[2:])

def json_to_ticket_envelope(json_obj) -> 'TicketEnvelope':
    return TicketEnvelope(
        attempt=json_obj["attempt"],
        signature=hex_to_bytes(json_obj["signature"])
    )

def json_to_ticket_body(json_obj) -> 'TicketBody':
    return TicketBody(
        id=hex_to_bytes(json_obj["id"]),
        attempt=json_obj["attempt"]
    )

def json_to_validator_data(json_obj) -> 'ValidatorData':
    return ValidatorData(
        bandersnatch=hex_to_bytes(json_obj["bandersnatch"]),
        ed25519=hex_to_bytes(json_obj["ed25519"]),
        bls=hex_to_bytes(json_obj["bls"]),
        metadata=hex_to_bytes(json_obj["metadata"])
    )

def json_to_state(json_obj) -> 'State':
    return State(
        tau=json_obj["tau"],
        eta=[hex_to_bytes(e) for e in json_obj["eta"]],
        lambda_=[json_to_validator_data(v) for v in json_obj["lambda"]],
        kappa=[json_to_validator_data(v) for v in json_obj["kappa"]],
        gamma_k=[json_to_validator_data(v) for v in json_obj["gamma_k"]],
        iota=[json_to_validator_data(v) for v in json_obj["iota"]],
        gamma_a=[json_to_ticket_body(tb) for tb in json_obj["gamma_a"]],
        gamma_s=SlotSealerSeries(
            keys=[hex_to_bytes(k) for k in json_obj["gamma_s"]["keys"]] if 'keys' in json_obj["gamma_s"] else [],
            tickets=[json_to_ticket_body(t) for t in json_obj["gamma_s"]["tickets"]] if 'tickets' in json_obj["gamma_s"] else [],
        ),
        gamma_z=hex_to_bytes(json_obj["gamma_z"])
    )

def json_to_input(json_obj) -> 'Input':
    return Input(
        slot=json_obj["slot"],
        entropy=hex_to_bytes(json_obj["entropy"]),
        extrinsic=[json_to_ticket_envelope(te) for te in json_obj["extrinsic"]]
    )

def json_to_ticket_body(ticket_json):
    return TicketBody(
        id=hex_to_bytes(ticket_json["id"]),
        attempt=ticket_json["attempt"]
    )
def json_to_output(json_obj) -> Output:
    """
    Convert JSON object to Output instance.
    :param json_obj: Dictionary representing JSON object of Output
    :return: Output instance
    """

    def parse_epoch_mark(epoch_json):
        return EpochMark(
            entropy=hex_to_bytes(epoch_json["entropy"]),
            validators=[hex_to_bytes(v) for v in epoch_json["validators"]]
        )

    # output = Output.deserialize(json_obj)

    # Parse the "ok" field, if present
    ok_data = json_obj.get("ok")
    if ok_data is not None:
        # Parse tickets_mark if present
        tickets_mark_data = ok_data.get("tickets_mark")
        tickets_mark = None
        if tickets_mark_data is not None:
            tickets_mark = [json_to_ticket_body(ticket) for ticket in tickets_mark_data]

        # Parse epoch_mark if present
        epoch_mark_data = ok_data.get("epoch_mark")
        epoch_mark = None
        if epoch_mark_data is not None:
            epoch_mark = parse_epoch_mark(epoch_mark_data)

        ok = OutputMarks(
            epoch_mark=epoch_mark,
            tickets_mark=tickets_mark
        )
    else:
        ok = None

    # Parse the "err" field, mapping to CustomErrorCode if present
    err_data = json_obj.get("err")
    err = CustomErrorCode[err_data] if err_data else None

    return Output(ok=ok, err=err)

def json_to_testcase(json_obj) -> 'Testcase':
    return Testcase(
        input=json_to_input(json_obj["input"]),
        pre_state=json_to_state(json_obj["pre_state"]),
        output=json_to_output(json_obj["output"]),
        post_state=json_to_state(json_obj["post_state"])
    )


def get_test_vector_files(directories: list, file_filter: Optional[str] = None):
    test_vectors = []
    for directory in directories:
        abs_dir = path.join(path.dirname(path.abspath(__file__)), 'fixtures', 'safrole', directory)
        for filename in os.listdir(str(abs_dir)):
            if filename.endswith('.json'):
                if file_filter is None or file_filter in filename:
                    test_vectors.append((f'{directory}_{filename}', directory, filename))
    return test_vectors


class TestMixinJSON(unittest.TestCase):

    maxDiff = None

    @staticmethod
    def load_test_vector_data(directory, test_vector_file):
        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'safrole', directory, test_vector_file
            )
        with open(test_vector_file) as f:
            return json.load(f)

    @staticmethod
    def load_test_vector_scale(directory, test_vector_file) -> bytes:
        test_vector_file = test_vector_file.replace('.json', '.scale')

        test_vector_file = path.join(
            path.dirname(path.abspath(__file__)), 'fixtures', 'safrole', directory, f'{test_vector_file}'
        )
        with open(test_vector_file, 'rb') as f:
            return f.read()

    @parameterized.expand(get_test_vector_files(['tiny'], file_filter=''))
    def test_serialize_mixin(self, name, directory, test_file):
        test_vector = self.load_test_vector_data(directory, test_file)

        test_case = Testcase.deserialize(test_vector)

        self.assertEqual(test_case, json_to_testcase(test_vector), "SerializeMixin.deserialize does not match")
        self.assertDictEqual(test_case.serialize(), test_vector, "SerializeMixin.serialize does not match")

        scale_bytes = self.load_test_vector_scale(directory, test_file)

        self.assertEqual(
            f'0x{scale_bytes.hex()}',
            test_case.to_scale_bytes().to_hex(),
            "SerializeMixin.to_scale_bytes does not match"
        )

        test_case = Testcase.from_scale_bytes(ScaleBytes(scale_bytes))
        self.assertEqual(test_case.to_scale_bytes().to_bytes(), scale_bytes, "SerializeMixin.from_scale_bytes does not match")


if __name__ == '__main__':
    unittest.main()
