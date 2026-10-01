"""Erros públicos da camada de dados Gold."""


class GoldDatabaseError(RuntimeError):
    """Erro base para falhas controladas ao abrir ou validar o Gold."""


class GoldUnavailableError(GoldDatabaseError):
    """O arquivo Gold não está acessível para leitura."""


class GoldInvalidError(GoldDatabaseError):
    """O arquivo existe, mas não corresponde a um Gold íntegro e esperado."""


class SqlValidationError(ValueError):
    """A consulta não atende às regras de leitura do módulo."""


class QueryTimeoutError(RuntimeError):
    """A consulta excedeu o tempo máximo permitido."""


class QueryExecutionError(RuntimeError):
    """A consulta foi permitida, mas falhou durante a execução."""


class ProviderConfigurationError(RuntimeError):
    """O adaptador de modelo não está configurado para executar."""
