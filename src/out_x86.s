section .bss
    _iobuf      resb 64

section .text
    global _start

_start:
    call main
    mov rdi, rax
    mov rax, 60
    syscall


_print_int:
    push rbp
    mov rbp, rsp
    push rbx
    mov rax, rdi
    lea rdi, [rel _iobuf + 31]
    mov byte [rdi], 10
    mov rbx, 0
    test rax, rax
    jns .pi_pos
    neg rax
    mov rbx, 1
.pi_pos:
    mov rcx, 10
.pi_loop:
    dec rdi
    xor rdx, rdx
    div rcx
    add dl, '0'
    mov [rdi], dl
    test rax, rax
    jnz .pi_loop
    test rbx, rbx
    jz .pi_nosign
    dec rdi
    mov byte [rdi], '-'
.pi_nosign:
    lea rax, [rel _iobuf + 32]
    mov rdx, rax
    sub rdx, rdi
    mov rsi, rdi
    mov rdi, 1
    mov rax, 1
    syscall
    pop rbx
    pop rbp
    ret

main:
    push rbp
    mov rbp, rsp
    sub rsp, 32

    mov rax, 14
    mov qword [rbp - 8], rax
    mov rax, qword [rbp - 8]
    mov qword [rbp - 16], rax
    mov rax, 14
    mov qword [rbp - 24], rax
    mov rdi, qword [rbp - 24]
    call _print_int
    mov rax, 0
    mov qword [rbp - 32], rax
    mov rax, qword [rbp - 32]
    mov rsp, rbp
    pop rbp
    ret

