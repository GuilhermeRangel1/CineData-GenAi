"""Erros controlados que podem ser convertidos em respostas públicas da API."""


class ErroDominio(Exception):
    """Erro de negócio com status e mensagem seguros para o cliente."""

    status_code = 500
    codigo = "ERRO_INTERNO"
    mensagem = "Não foi possível concluir a operação."
    headers: dict[str, str] | None = None


class FilmeNaoEncontradoError(ErroDominio):
    """Filme solicitado não existe no catálogo."""

    status_code = 404
    codigo = "FILME_NAO_ENCONTRADO"
    mensagem = "Filme não encontrado."


class FilmeConflitoError(ErroDominio):
    """Escrita de filme conflita com uma restrição de integridade."""

    status_code = 409
    codigo = "CONFLITO_DE_DADOS"
    mensagem = "Não foi possível concluir a operação devido a um conflito de dados."


class FilmePersistenceError(ErroDominio):
    """Falha inesperada de persistência durante uma escrita de filme."""

    status_code = 500
    codigo = "FALHA_DE_PERSISTENCIA"
    mensagem = "Não foi possível concluir a operação no momento."


class UsuarioJaExisteError(ErroDominio):
    """O e-mail informado já pertence a uma conta."""

    status_code = 409
    codigo = "USUARIO_JA_EXISTE"
    mensagem = "Já existe uma conta com este e-mail. Tente entrar ou use outro endereço."


class CredenciaisInvalidasError(ErroDominio):
    """O login não pode revelar qual credencial está incorreta."""

    status_code = 401
    codigo = "CREDENCIAIS_INVALIDAS"
    mensagem = "E-mail ou senha inválidos. Confira os dados e tente novamente."


class ConfiguracaoAutenticacaoError(ErroDominio):
    """A aplicação não recebeu a chave necessária para assinar tokens."""

    status_code = 503
    codigo = "AUTENTICACAO_INDISPONIVEL"
    mensagem = "A autenticação não está disponível no momento."


class TokenInvalidoError(ErroDominio):
    """O token Bearer está ausente, expirado ou não é confiável."""

    status_code = 401
    codigo = "TOKEN_INVALIDO"
    mensagem = "É necessário iniciar uma sessão válida para esta operação."
    headers = {"WWW-Authenticate": "Bearer"}


class PermissaoNegadaError(ErroDominio):
    """A conta autenticada não possui o papel exigido pela operação."""

    status_code = 403
    codigo = "PERMISSAO_NEGADA"
    mensagem = "Sua conta não possui permissão para esta operação."


class ListaNaoEncontradaError(ErroDominio):
    """Lista solicitada não existe ou não pertence à conta autenticada."""

    status_code = 404
    codigo = "LISTA_NAO_ENCONTRADA"
    mensagem = "Lista não encontrada."


class ConversationNotFoundError(ErroDominio):
    """A conversa não existe ou pertence a outra conta."""

    status_code = 404
    codigo = "CONVERSA_NAO_ENCONTRADA"
    mensagem = "Conversa não encontrada."


class FilmeJaEstaNaListaError(ErroDominio):
    """Evita que a mesma lista contenha o mesmo filme mais de uma vez."""

    status_code = 409
    codigo = "FILME_JA_ESTA_NA_LISTA"
    mensagem = "Este filme já está na lista."


class PerfilNaoEncontradoError(ErroDominio):
    """Perfil público solicitado não existe."""

    status_code = 404
    codigo = "PERFIL_NAO_ENCONTRADO"
    mensagem = "Perfil não encontrado."


class SolicitacaoAmizadeInvalidaError(ErroDominio):
    """Impede que uma conta envie um pedido para si mesma."""

    status_code = 422
    codigo = "SOLICITACAO_AMIZADE_INVALIDA"
    mensagem = "Não é possível enviar uma solicitação de amizade para si mesmo."


class SolicitacaoAmizadeNaoEncontradaError(ErroDominio):
    """Pedido solicitado não existe ou não pode ser respondido pela conta."""

    status_code = 404
    codigo = "SOLICITACAO_AMIZADE_NAO_ENCONTRADA"
    mensagem = "Solicitação de amizade não encontrada."


class AmizadeConflitoError(ErroDominio):
    """Evita pedidos repetidos e reaproximações bloqueadas."""

    status_code = 409
    codigo = "AMIZADE_EM_CONFLITO"
    mensagem = "Já existe uma solicitação, amizade ou bloqueio entre estas contas."


class ComunidadeNaoEncontradaError(ErroDominio):
    status_code = 404
    codigo = "COMUNIDADE_NAO_ENCONTRADA"
    mensagem = "Comunidade não encontrada."


class ComunidadeConflitoError(ErroDominio):
    status_code = 409
    codigo = "COMUNIDADE_EM_CONFLITO"
    mensagem = "Já existe uma comunidade com este nome."


class PublicacaoComunidadeNaoEncontradaError(ErroDominio):
    status_code = 404
    codigo = "PUBLICACAO_NAO_ENCONTRADA"
    mensagem = "Publicação não encontrada."


class ComentarioComunidadeNaoEncontradoError(ErroDominio):
    status_code = 404
    codigo = "COMENTARIO_NAO_ENCONTRADO"
    mensagem = "Comentário não encontrado."


class PublicacaoModeradaError(ErroDominio):
    status_code = 409
    codigo = "PUBLICACAO_MODERADA"
    mensagem = "Esta mensagem foi removida pela moderação e não aceita novas interações."


class ParticipacaoComunidadeNecessariaError(ErroDominio):
    status_code = 403
    codigo = "PARTICIPACAO_NECESSARIA"
    mensagem = "Entre na comunidade para realizar esta ação."


class ParticipacaoComunidadeConflitoError(ErroDominio):
    status_code = 409
    codigo = "PARTICIPACAO_EM_CONFLITO"
    mensagem = "A pessoa já participa desta comunidade."


class FonteExternaIndisponivelError(ErroDominio):
    """A fonte de metadados não está configurada ou não respondeu com segurança."""

    status_code = 503
    codigo = "FONTE_EXTERNA_INDISPONIVEL"
    mensagem = "A fonte externa de filmes não está disponível no momento."
