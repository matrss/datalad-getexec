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
          pkgs = import inputs.nixpkgs { inherit system; };
          python-env = pkgs.python3.withPackages (ps: with ps; [
            pip
          ]);
        in
        {
          default = pkgs.mkShell {
            nativeBuildInputs = with pkgs; [ python-env ];
            shellHook = ''
              export PIP_PREFIX=$(pwd)/_build/pip_packages
              export PYTHONPATH="$PIP_PREFIX/${python-env.sitePackages}:$PYTHONPATH"
              export PATH="$PIP_PREFIX/bin:$PATH"
              unset SOURCE_DATE_EPOCH
            '';
          };
        });
    };
}
