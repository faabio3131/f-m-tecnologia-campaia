# WP-R03-02B — Validação isolada de imagens (16/10/2026)

## CURRENT e escopo
main@ff5586ab6698324e62bb47df14589ab67c2dd0c2, após PR #65:
HEAD 4a54e3ac62c53f624aa38f78b84f92c3829c937b com CI Backend 38844316693,
Frontend 38844316728, F4 38844316684; pós-merge 38844545603, 38844545620,
38844545606, todos verdes. Contrato/adaptador privado GCS preservados.

Antes de ligar upload, a assinatura PNG do transporte não prova imagem válida. Este
WP acrescenta o processamento isolado; não abre endpoint nem ativa armazenamento.
Pillow 12.3.0 publicado em 01/07/2026, conferido na documentação estável/PyPI em
16/10/2026, pinado e sujeito ao pip-audit sem exceções.

## Implementação
Entrada/saída limitadas a 5 MiB; PNG, JPEG e WebP estáticos. SVG/EPS/GIF/BMP,
animações, imagens truncadas e excesso de dimensão/pixels são rejeitados.
Máximo 4.194.304 pixels e dimensão individual 8.192; não altera quota comercial.

Worker Python -I -B com script absoluto fixo, sem shell, close_fds e ambiente mínimo
sem credenciais/proxy/variáveis da aplicação. O pai limita tempo de parede a 10s,
entrada/saída por pipes não bloqueantes, mata o processo em timeout/excesso e
verifica envelope PNG sem executar Pillow no processo API.

Filho aplica RLIMIT_AS 160 MiB, CPU 4/5s, NOFILE 16, FSIZE 5 MiB e CORE 0.
Pré-carrega bibliotecas confiáveis e instala filtro Linux seccomp antes de ler bytes.
Verifica ABI x86_64/aarch64 e permite apenas syscalls básicos de memória/pipes/sinal/
tempo/saída. Não permite abrir arquivos, socket/rede, exec, fork/clone, ptrace ou
io_uring. Plataforma/kernel sem suporte falha fechada, sem fallback sem filtro.

Após verify/load, aplica orientação EXIF e copia pixels para imagem RGB/RGBA nova.
Preserva transparência; não propaga EXIF/XMP/ICC/comentários. Pai confere CRC,
IHDR com dimensões/modo permitidos, IDAT e IEND; rejeita chunks extras e bytes
posteriores. Verificação do envelope não é um segundo decoder nem certificado antimalware.

## Verificação e limites
Testes reais do worker cobrem formatos aceitos, transparência/paleta, EXIF/orientação,
metadados removidos, animação/formato inválido/truncamento, limites, isolamento do
ambiente e envelope adulterado. Testes de processo hostil provam limite de saída e
timeout com encerramento; probe do filtro prova negação de arquivo/rede/fork.
CI F4 também executa normalização no container de produção como usuário campaia.
A CI completa no HEAD exato e pós-merge deve ser registrada após os workflows.

O filtro é uma camada de isolamento, não sandbox completo nem pentest independente.
Compatibilidade no runtime Cloud Run real ainda precisa de homologação autorizada;
nenhuma alegação de suporte foi inferida apenas de Linux/CI.
Faltam semáforo/limite de concorrência no endpoint, rate limit, auth antes de upload,
quota/fence persistentes, API/Web e GCS real. F6 continua PARTIAL e F16 permanece aberto.
Nenhum deploy, migração real, credencial, SQL, bucket ou gasto foi ativado.

## Referências primárias
- https://pillow.readthedocs.io/en/stable/handbook/security.html
- https://pillow.readthedocs.io/en/stable/releasenotes/12.3.0.html
- https://pypi.org/project/pillow/
- https://docs.kernel.org/userspace-api/seccomp_filter.html
- https://github.com/torvalds/linux/blob/master/arch/x86/entry/syscalls/syscall_64.tbl
- https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/unistd.h
- https://github.com/torvalds/linux/blob/master/include/uapi/linux/seccomp.h
- https://github.com/torvalds/linux/blob/master/include/uapi/linux/filter.h
- https://github.com/torvalds/linux/blob/master/include/uapi/linux/bpf_common.h
- https://github.com/torvalds/linux/blob/master/include/uapi/linux/prctl.h
- https://github.com/torvalds/linux/blob/master/include/uapi/linux/audit.h
- https://github.com/torvalds/linux/blob/master/include/uapi/linux/elf-em.h
