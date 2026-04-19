
    .data

    .text
    .globl main

    .globl _start
_start:
    call  main
    li    a7, 10
    ecall

main:
    addi  sp, sp, -32
    sw    ra, 28(sp)
    sw    s0, 24(sp)
    addi  s0, sp, 32

    li    t0, 14
    sw    t0, -12(s0)
    sw    t0, -16(s0)
    li    t0, 14
    sw    t0, -20(s0)
    lw    a0, -20(s0)
    li    a7, 1
    ecall
    li    a0, 10
    li    a7, 11
    ecall
    li    t0, 0
    sw    t0, -24(s0)
    lw    a0, -24(s0)
    lw    ra, 28(sp)
    lw    s0, 24(sp)
    addi  sp, sp, 32
    ret
