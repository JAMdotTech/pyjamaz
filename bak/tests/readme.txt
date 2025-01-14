openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -config cert.cnf

simple echo test:
python bak/tests/echo_server.py
python bak/tests/echo_client.py

using protocol:
python bak/tests/test_node.py --host ::1 -p 9000 -k ./pyjamaz/data/alice/alice.key -c ./pyjamaz/data/alice/alice.pem
python bak/tests/test_node.py --host ::1 -p 9001 -k ./pyjamaz/data/john/john.key -c ./pyjamaz/data/john/john.pem
