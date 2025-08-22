rm -rf ./build

pip install pyc_wheel
python3.12 -m build --wheel
mv dist/pyjamaz-0.1.4-py3-none-any.whl dist/pyjamaz-0.1.4-cp312-none-any.whl
python3.12 -m pyc_wheel dist/pyjamaz-0.1.4-cp312-none-any.whl

pip install dist/pyjamaz-0.1.4-cp312-none-any.whl --force-reinstall

pip install pyinstaller
pyinstaller --onefile --name pyjamaz --collect-data pyjamaz  "$(which pyjamaz)"
