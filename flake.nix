{
  description = "DataLad extension for code execution in get commands";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";

  outputs = inputs:
    let
      systems = [ "x86_64-linux" ];
      forAllSystems = inputs.nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (system:
        let
          pkgs = inputs.nixpkgs.legacyPackages.${system};
          python-env = pkgs.python3.withPackages (ps: with ps; [
            setuptools
            pip
            virtualenv
            tox
          ]);
        in
        {
          default = pkgs.mkShell {
            nativeBuildInputs = with pkgs; [ python-env ];
          };
        });
    };
}
