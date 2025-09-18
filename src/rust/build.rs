fn main() {
    // Link to the C++ library
    println!("cargo:rustc-link-search=native=../../build/cpp");
    println!("cargo:rustc-link-lib=qadataswap_core");

    // Also link required system libraries
    println!("cargo:rustc-link-lib=rt");
    println!("cargo:rustc-link-lib=pthread");

    // Add Arrow library path
    println!("cargo:rustc-link-search=native=/usr/lib/x86_64-linux-gnu");
    println!("cargo:rustc-link-lib=arrow");

    // Tell cargo to rerun if the library changes
    println!("cargo:rerun-if-changed=../../build/cpp/libqadataswap_core.so");
}