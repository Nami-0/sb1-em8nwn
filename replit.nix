{pkgs}: {
  deps = [
    pkgs.lsof
    pkgs.redis
    pkgs.openssl
    pkgs.postgresql
  ];
}
