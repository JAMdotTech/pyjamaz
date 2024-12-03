def convert_duna_state_trace(trace_data: dict) -> dict:
    trace_data["timeslot"] = {"number": trace_data.pop("tau")}
    trace_data["entropy"] = {"entropy": trace_data.pop("eta")}
    trace_data["safrole"] = {
        "ticket_accumulator": trace_data["gamma"]["gamma_a"],
        "validators": trace_data["gamma"]["gamma_k"],
        "slot_sealer_series": trace_data["gamma"]["gamma_s"],
        "ring_commitment": trace_data["gamma"]["gamma_z"]
    }
    del trace_data["gamma"]

    trace_data["validator_queue"] = {"validators": trace_data.pop("iota")}
    trace_data["validator_pool"] = {"validators": trace_data.pop("kappa")}
    trace_data["validator_archive"] = {"validators": trace_data.pop("lambda")}
    trace_data["authorizer_pools"] = {"authorizer_pools": trace_data.pop("alpha")}
    trace_data["recent_history"] = {"recent_history": trace_data.pop("beta") or []}

    trace_data["authorizer_queues"] = {"authorizer_queues": trace_data.pop("varphi")}
    trace_data["disputes"] = {
        "good_set": trace_data["psi"]["good"],
        "bad_set": trace_data["psi"]["bad"],
        "wonky_set": trace_data["psi"]["wonky"],
        "offenders": trace_data["psi"]["offenders"],
    }
    del trace_data["psi"]
    trace_data["statistics"] = {"statistics": [
        [
            {
                "blocks": stats['block_number'],
                "tickets": stats['ticket_number'],
                "preimages": stats['preimage_number'],
                "preimage_bytes": stats['octets_number'],
                "guarantees": stats['report_number'],
                "assurances": stats['availability_number'],
            } for stats in section
        ] for section in trace_data['pi']
    ]}
    trace_data["services"] = {"services": {}}
    trace_data["assurances"] = {"assurances": trace_data.pop('rho')}
    trace_data["privileged_services"] = {
        "empower_service": 0,
        "assign_service": 0,
        "designate_service": 0,
        "auto_accumulate_services": {}
    }
    trace_data["accumulation_queue"] = {"accumulation_queue": [[], [], [], [], [], [], [], [], [], [], [], []]}
    trace_data["accumulation_history"] = {
        "accumulation_history": ["0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000",
                                 "0x0000000000000000000000000000000000000000000000000000000000000000"]}
    del trace_data["chi"]
    del trace_data["pi"]
    del trace_data["theta"]
    del trace_data["xi"]
    del trace_data["service_account"]
    return trace_data
