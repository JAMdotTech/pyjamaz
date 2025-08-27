rm -rf ./build

pip install pyc_wheel
python3.12 -m build --wheel
mv dist/pyjamaz-0.1.5-py3-none-any.whl dist/pyjamaz-0.1.5-cp312-none-any.whl
python3.12 -m pyc_wheel dist/pyjamaz-0.1.5-cp312-none-any.whl

pip install dist/pyjamaz-0.1.5-cp312-none-any.whl --force-reinstall

pip install pyinstaller
pyinstaller --onefile --name pyjamaz --collect-data pyjamaz  "$(which pyjamaz)"
zip dist/pyjamaz-0.1.5-linux-x86_64.zip dist/pyjamaz
