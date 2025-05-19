from prometheus_client import Gauge, Info, Counter

client_info = Info('client_info', 'Client info')
tickets_accumulator_count = Gauge('tickets', 'Number of tickets accumulated')
total_workreports_accumulated = Counter('total_workreports', 'Total of workreports accumulated')
current_timeslot_gauge = Gauge('current_timeslot', 'Current timeslot')
state_timeslot_gauge = Gauge('state_timeslot', 'Latest timeslot')
connected_clients_gauge = Gauge('connected_clients', 'Connected clients')
