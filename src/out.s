
    .section .data
_fmt_int:  .string "%ld\n"
_fmt_uint: .string "%lu\n"
_fmt_char: .string "%c\n"
_fmt_str:  .string "%s\n"
_fmt_scan: .string "%ld"

    .section .text
    .global main

main:
    addi  sp, sp, -384
    sd    ra, 376(sp)
    sd    s0, 368(sp)
    addi  s0, sp, 384

    li    t0, 5
    sd    t0, -24(s0)
    ld    t0, -24(s0)
    sd    t0, -32(s0)
    
    li    t0, 6
    sd    t0, -40(s0)
    ld    t0, -40(s0)
    sd    t0, -48(s0)
    li    t0, 21
    sd    t0, -56(s0)
    ld    t0, -56(s0)
    sd    t0, -64(s0)
    li    t0, 5
    sd    t0, -72(s0)
    ld    t0, -72(s0)
    sd    t0, -80(s0)
    li    t0, 2
    sd    t0, -88(s0)
    ld    t0, -88(s0)
    sd    t0, -96(s0)
    li    t0, 30
    sd    t0, -104(s0)
    ld    t0, -104(s0)
    sd    t0, -112(s0)
    li    t0, -7
    sd    t0, -120(s0)
    ld    t0, -120(s0)
    sd    t0, -128(s0)
    li    t0, 1
    sd    t0, -136(s0)
    ld    t0, -136(s0)
    sd    t0, -144(s0)
    li    t0, 1
    sd    t0, -152(s0)
    ld    t0, -152(s0)
    sd    t0, -160(s0)
    li    t0, 0
    sd    t0, -168(s0)
    ld    t0, -168(s0)
    sd    t0, -176(s0)
    li    t0, 1
    sd    t0, -184(s0)
    ld    t0, -184(s0)
    sd    t0, -192(s0)
    li    t0, 0
    sd    t0, -200(s0)
    ld    t0, -200(s0)
    sd    t0, -208(s0)
    li    t0, 1
    sd    t0, -216(s0)
    ld    t0, -216(s0)
    sd    t0, -224(s0)
    li    t0, 0
    sd    t0, -232(s0)
    ld    t0, -232(s0)
    sd    t0, -240(s0)
    li    t0, 1
    sd    t0, -248(s0)
    ld    t0, -248(s0)
    sd    t0, -256(s0)
    li    t0, 1
    sd    t0, -264(s0)
    ld    t0, -264(s0)
    sd    t0, -272(s0)
    li    t0, 42
    sd    t0, -280(s0)
    ld    t0, -280(s0)
    sd    t0, -288(s0)
    j     .Lmain_L1
.Lmain_L0:
.Lmain_L1:
    ld    t0, -32(s0)
    sd    t0, -296(s0)
    ld    t0, -48(s0)
    sd    t0, -304(s0)
    ld    t0, -64(s0)
    sd    t0, -312(s0)
    ld    t0, -80(s0)
    sd    t0, -320(s0)
    ld    t0, -96(s0)
    sd    t0, -328(s0)
    ld    t0, -112(s0)
    sd    t0, -336(s0)
    ld    t0, -128(s0)
    sd    t0, -344(s0)
    la    a0, _fmt_int
    ld    a1, -296(s0)
    call  printf
    la    a0, _fmt_int
    ld    a1, -304(s0)
    call  printf
    la    a0, _fmt_int
    ld    a1, -312(s0)
    call  printf
    la    a0, _fmt_int
    ld    a1, -320(s0)
    call  printf
    la    a0, _fmt_int
    ld    a1, -328(s0)
    call  printf
    la    a0, _fmt_int
    ld    a1, -336(s0)
    call  printf
    la    a0, _fmt_int
    ld    a1, -344(s0)
    call  printf
    ld    t0, -160(s0)
    sd    t0, -352(s0)
    ld    t0, -176(s0)
    sd    t0, -360(s0)
    ld    t0, -192(s0)
    sd    t0, -368(s0)
    la    a0, _fmt_int
    ld    a1, -352(s0)
    call  printf
    la    a0, _fmt_int
    ld    a1, -360(s0)
    call  printf
    la    a0, _fmt_int
    ld    a1, -368(s0)
    call  printf
    li    t0, 0
    sd    t0, -376(s0)
    ld    a0, -376(s0)
    call  exit
    li    t0, 0
    sd    t0, -384(s0)
    ld    a0, -384(s0)
    ld    ra, 376(sp)
    ld    s0, 368(sp)
    addi  sp, sp, 384
    ret
