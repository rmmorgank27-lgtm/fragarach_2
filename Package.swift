// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "FragarachIIOperationsConsole",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "OperationsCore", targets: ["OperationsCore"]),
        .executable(name: "FragarachII", targets: ["FragarachII"]),
        .executable(name: "OperationsCoreChecks", targets: ["OperationsCoreChecks"]),
    ],
    targets: [
        .systemLibrary(name: "CSQLite", path: "Sources/CSQLite"),
        .target(name: "OperationsCore", dependencies: ["CSQLite"]),
        .executableTarget(name: "FragarachII", dependencies: ["OperationsCore"]),
        .executableTarget(name: "OperationsCoreChecks", dependencies: ["OperationsCore"]),
    ]
)
