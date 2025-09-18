use std::path::Path;
use std::env;

fn main() {
    // Get the absolute path to the C++ library
    let manifest_dir = env::var("CARGO_MANIFEST_DIR").unwrap();
    let cpp_lib_path = Path::new(&manifest_dir).join("../../build/cpp").canonicalize();

    if let Ok(lib_path) = cpp_lib_path {
        let lib_file = lib_path.join("libqadataswap_core.so");

        if lib_file.exists() {
            let lib_dir = lib_path.to_string_lossy();

            // Link to the C++ library
            println!("cargo:rustc-link-search=native={}", lib_dir);
            println!("cargo:rustc-link-lib=dylib=qadataswap_core");

            // Also link required system libraries
            println!("cargo:rustc-link-lib=rt");
            println!("cargo:rustc-link-lib=pthread");

            // Add Arrow library path
            println!("cargo:rustc-link-search=native=/usr/lib/x86_64-linux-gnu");
            println!("cargo:rustc-link-lib=arrow");

            // Link C++ standard library
            println!("cargo:rustc-link-lib=stdc++");

            // Tell cargo to rerun if the library changes
            println!("cargo:rerun-if-changed={}", lib_file.to_string_lossy());

            println!("cargo:warning=Linking to C++ library: {}", lib_file.to_string_lossy());
        } else {
            println!("cargo:warning=C++ library not found, skipping FFI linking");
            println!("cargo:warning=Building with mock implementation");
        }
    } else {
        println!("cargo:warning=Could not resolve C++ library path, skipping FFI linking");
        println!("cargo:warning=Building with mock implementation");
    }
}