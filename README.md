# ProvaFácil Flask Completo

## Recursos
- Multiusuário, login e autocadastro público de contas comuns
- Gestão administrativa de usuários: perfis Admin/Usuário, ativação, edição, exclusão e reset de senha
- CRUD completo de questões, duplicação, pesquisa, filtro e importação XLSX/CSV/TXT
- Provas aleatórias por assunto, realização online e histórico privado detalhado
- Impressão A4 da prova para resposta manual
- Gabarito impresso exclusivo do Admin
- O botão de impressão do navegador também permite salvar como PDF
- Estatísticas por prova: pessoas distintas, tentativas, média, média percentual e aprovação
- Ativação/desativação de provas
- Download de backup SQLite pelo Admin

## Rodar localmente
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```
No Windows: `.venv\Scripts\activate`.

Acesse `http://localhost:5000`.

## Docker
```bash
docker compose up --build
```

## Primeiro acesso
- Usuário: `admin`
- Senha: `admin123`

Troque `SECRET_KEY` e `ADMIN_PASSWORD` antes da primeira inicialização.

## Formato da importação
`Assunto|Enunciado|AlternativaA|AlternativaB|AlternativaC|AlternativaD|AlternativaCorreta|Justificativa`

## Impressão e PDF
Abra uma prova e clique em **Imprimir**. Na janela do navegador, selecione uma impressora física ou **Salvar como PDF**. O Admin também pode imprimir o gabarito pelo menu Provas.

## Autocadastro
A página inicial e a tela de login exibem o link **Cadastre-se**. O autocadastro cria somente contas comuns e ativas. A promoção para Administrador continua restrita à gestão de usuários do Admin. São validados nome, login único, senha mínima de 6 caracteres e confirmação de senha.
# provafacil
