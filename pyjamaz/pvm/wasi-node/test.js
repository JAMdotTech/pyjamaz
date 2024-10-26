async function main() {
    const fs = require("fs");
    const { WASI } = require("wasi");
    const wasi = new WASI();
    const importObject = {
        wasi_snapshot_preview1: wasi.wasiImport,
        js: {
            cpu_time: (time) => (Date.now() / 1000), // Date.now() returns milliseconds, so divide by 1000
            wasm_test: () => console.log("WOEI!?") // Date.now() returns milliseconds, so divide by 1000
        }
    };
    const wasm = await WebAssembly.compile(fs.readFileSync("/usr/src/test2.js"));
    const instance = await WebAssembly.instantiate(wasm, importObject);
    wasi.start(instance);
}
main();

