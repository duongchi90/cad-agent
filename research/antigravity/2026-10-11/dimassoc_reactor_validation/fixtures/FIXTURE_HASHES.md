# Synthetic Fixture Hashes and Provenance

## Environment
- Host Platform: Windows 11 x64
- CAD Engine: Autodesk AutoCAD 2027 Commercial / Preview (64-bit)
- Headless Runner: `accoreconsole.exe`
- Target Database: ModelSpace native 2D geometry

## Fixture Identifiers & Hashes

| Fixture ID | DIMASSOC | Description | SHA-256 Checksum | Generator Script |
| :--- | :---: | :--- | :--- | :--- |
| `FIXTURE_A` | `1` | Non-associative Line (0,0 to 100,0) and AlignedDimension (len 100) | `836abde79f70684ae1e1bec4ebb2aedda9256ed872072c11d3eca3bc094b45cb` | `fixtures/gen_fixture_a.scr` |
| `FIXTURE_B` | `2` | Associative Line (0,0 to 100,0) and AlignedDimension (len 100) | `47c8d9f7b1a3286efdbcd917653ac8a9d7642b6d0eb3a827eb7e93993b2361e8` | `fixtures/gen_fixture_b.scr` / `fixtures/create_b.lsp` |

## Reproduction Steps

### Fixture A (DIMASSOC=1)
Execute headlessly in fresh drawing:
```cmd
"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe" /s fixtures/gen_fixture_a.scr
```

### Fixture B (DIMASSOC=2)
Execute headlessly in fresh drawing:
```cmd
"C:\Program Files\Autodesk\AutoCAD 2027\accoreconsole.exe" /s fixtures/gen_fixture_b.scr
```
