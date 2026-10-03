"""Casos de uso do domínio de filmes."""

import logging
from math import ceil
from uuid import uuid4

from sqlalchemy import and_, case, func, or_, select, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import load_only, selectinload

from app.api.v1.schemas import MetadadosPagina, Pagina
from app.core.config import get_settings
from app.core.errors import (
    FilmeConflitoError,
    FilmeNaoEncontradoError,
    FilmePersistenceError,
    FonteExternaIndisponivelError,
)
from app.integrations.tmdb import TmdbGateway
from app.movies.models import (
    DimCompany,
    DimGenre,
    DimMovie,
    DimPerson,
    DimReview,
    FactMoviePerformance,
    MovieReview,
    PersonType,
    bridge_movie_company,
    bridge_movie_person,
)
from app.movies.schemas import (
    AvaliacaoCriacao,
    AvaliacaoLeitura,
    ConsultaCatalogo,
    DesempenhoFilme,
    FilmeAtualizacao,
    FilmeCriacao,
    FilmeDetalhe,
    FilmeResumo,
    GeneroResumo,
    PessoaResumo,
    ProdutoraResumo,
    TrailerFilme,
)
from app.users.models import User

logger = logging.getLogger(__name__)
NOTA_PRIOR = 6.0
VOTOS_PRIOR = 500
DETALHE_LOAD_OPTIONS = (
    selectinload(DimMovie.genres),
    selectinload(DimMovie.people),
    selectinload(DimMovie.companies),
    selectinload(DimMovie.performance),
    selectinload(DimMovie.reviews_summary),
    selectinload(DimMovie.reviews),
)


class CatalogoFilmesService:
    """Consulta o catálogo sem expor detalhes do ORM à camada HTTP."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def listar(self, consulta: ConsultaCatalogo) -> Pagina[FilmeResumo]:
        """Retorna um catálogo filtrado, ordenado e paginado de forma estável."""

        # Ordena apenas as chaves. Carregar sinopses, URLs e relações antes do
        # LIMIT faz o SQLite transportar muito mais dados pela ordenação.
        statement = select(DimMovie.sk_movie_id)

        if consulta.busca:
            movie_ids = self._ids_busca(
                consulta.busca,
                "dim_movies_search",
                "sk_movie_id",
                DimMovie.sk_movie_id,
                DimMovie.titulo,
            )
            existe_titulo_local = await self._session.scalar(
                select(DimMovie.sk_movie_id)
                .where(DimMovie.sk_movie_id.in_(movie_ids))
                .limit(1)
            )
            condicoes_titulo = [DimMovie.sk_movie_id.in_(movie_ids)]

            # A base local pode guardar o título original/em inglês. Quando o
            # termo não existe nela, o TMDB fornece as traduções equivalentes
            # para recuperarmos o mesmo registro, sem criar uma cópia.
            if existe_titulo_local is None and len(consulta.busca.strip()) >= 3:
                try:
                    titulos_equivalentes = await TmdbGateway(
                        get_settings().tmdb_api_token
                    ).buscar_titulos_equivalentes(consulta.busca)
                except FonteExternaIndisponivelError:
                    titulos_equivalentes = set()
                if titulos_equivalentes:
                    condicoes_titulo.append(
                        func.lower(DimMovie.titulo).in_(titulos_equivalentes)
                    )
            statement = statement.where(or_(*condicoes_titulo))

        if consulta.genero:
            genero_id = await self._session.scalar(
                select(DimGenre.sk_genre_id).where(
                    func.lower(DimGenre.nome_genero) == consulta.genero.casefold()
                )
            )
            if genero_id is None:
                return Pagina(
                    itens=[],
                    meta=MetadadosPagina(
                        pagina=consulta.pagina,
                        tamanho_pagina=consulta.tamanho_pagina,
                        total_itens=0,
                        total_paginas=0,
                    ),
                )
            statement = statement.join(DimMovie.genres).where(DimGenre.sk_genre_id == genero_id)

        if consulta.pessoa:
            pessoa_ids = self._ids_busca(
                consulta.pessoa,
                "dim_people_search",
                "sk_person_id",
                DimPerson.sk_person_id,
                DimPerson.nome_pessoa,
            )
            movie_ids = select(bridge_movie_person.c.sk_movie_id).where(
                bridge_movie_person.c.sk_person_id.in_(pessoa_ids)
            )
            statement = statement.where(DimMovie.sk_movie_id.in_(movie_ids))

        if consulta.produtora:
            company_ids = self._ids_busca(
                consulta.produtora,
                "dim_companies_search",
                "sk_company_id",
                DimCompany.sk_company_id,
                DimCompany.nome_produtora,
            )
            movie_ids = select(bridge_movie_company.c.sk_movie_id).where(
                bridge_movie_company.c.sk_company_id.in_(company_ids)
            )
            statement = statement.where(DimMovie.sk_movie_id.in_(movie_ids))

        if consulta.ano_inicial:
            statement = statement.where(
                DimMovie.ano_lancamento.is_not(None),
                DimMovie.ano_lancamento >= consulta.ano_inicial,
            )
        if consulta.ano_final:
            statement = statement.where(
                DimMovie.ano_lancamento.is_not(None), DimMovie.ano_lancamento <= consulta.ano_final
            )
        if consulta.duracao_minima:
            statement = statement.where(
                DimMovie.duracao_minutos.is_not(None),
                DimMovie.duracao_minutos >= consulta.duracao_minima,
            )
        if consulta.duracao_maxima:
            statement = statement.where(
                DimMovie.duracao_minutos.is_not(None),
                DimMovie.duracao_minutos <= consulta.duracao_maxima,
            )
        if consulta.nota_minima is not None:
            statement = statement.where(
                DimMovie.reviews_summary.has(
                    and_(DimReview.nota_media_usuarios >= consulta.nota_minima)
                )
            )
        if consulta.somente_com_trailer:
            statement = statement.where(DimMovie.url_trailer.is_not(None))

        # As relações do catálogo são únicas por chave no schema; não há linhas
        # duplicadas a eliminar. Evitar DISTINCT mantém o filtro por gênero
        # indexável mesmo com o catálogo Gold completo.
        count_statement = select(func.count()).select_from(*statement.get_final_froms())
        if statement.whereclause is not None:
            count_statement = count_statement.where(statement.whereclause)
        total = await self._session.scalar(count_statement)
        total_itens = total or 0

        if consulta.ordenar_por == "relevancia":
            # A média Bayesiana reduz o efeito de notas perfeitas com poucas
            # avaliações e favorece filmes reconhecidos sem esconder boas notas.
            statement = statement.outerjoin(
                FactMoviePerformance,
                FactMoviePerformance.sk_movie_id == DimMovie.sk_movie_id,
            )
            votos = func.coalesce(FactMoviePerformance.qtd_tmdb, 0)
            nota = FactMoviePerformance.nota_tmdb
            nota_ponderada = (nota * votos + NOTA_PRIOR * VOTOS_PRIOR) / (
                votos + VOTOS_PRIOR
            )
            pontuacao_relevancia = case(
                (nota.is_not(None) & (votos > 0), nota_ponderada),
                else_=None,
            )
            ordenacao = [
                pontuacao_relevancia.desc().nullslast(),
                FactMoviePerformance.popularidade.desc().nullslast(),
                votos.desc(),
                DimMovie.titulo.asc(),
                DimMovie.id_filme.asc(),
            ]
        else:
            campo_ordenacao = getattr(DimMovie, consulta.ordenar_por)
            ordem_primaria = (
                campo_ordenacao.asc()
                if consulta.direcao == "asc"
                else campo_ordenacao.desc()
            )
            ordenacao = [ordem_primaria, DimMovie.titulo.asc(), DimMovie.id_filme.asc()]
        if consulta.priorizar_capa:
            # Um backdrop também permite uma capa útil no card, quando não há pôster.
            ordenacao.insert(
                0, (DimMovie.url_poster.is_(None) & DimMovie.url_backdrop.is_(None)).asc()
            )
        if consulta.priorizar_trailer:
            ordenacao.insert(0, DimMovie.url_trailer.is_(None).asc())
        offset = (consulta.pagina - 1) * consulta.tamanho_pagina
        result = await self._session.scalars(
            statement.order_by(*ordenacao).offset(offset).limit(consulta.tamanho_pagina)
        )
        movie_ids = list(result)
        if movie_ids:
            filmes_resultado = await self._session.scalars(
                select(DimMovie)
                .where(DimMovie.sk_movie_id.in_(movie_ids))
                .options(
                    load_only(
                        DimMovie.sk_movie_id,
                        DimMovie.id_filme,
                        DimMovie.titulo,
                        DimMovie.ano_lancamento,
                        DimMovie.url_poster,
                        DimMovie.url_backdrop,
                    ),
                    selectinload(DimMovie.genres),
                    selectinload(DimMovie.reviews_summary),
                )
            )
            filmes_por_id = {filme.sk_movie_id: filme for filme in filmes_resultado}
            filmes = [filmes_por_id[movie_id] for movie_id in movie_ids]
        else:
            filmes = []

        return Pagina(
            itens=[self._para_resumo(filme) for filme in filmes],
            meta=MetadadosPagina(
                pagina=consulta.pagina,
                tamanho_pagina=consulta.tamanho_pagina,
                total_itens=total_itens,
                total_paginas=ceil(total_itens / consulta.tamanho_pagina),
            ),
        )

    async def obter_detalhe(self, filme_id: str) -> FilmeDetalhe:
        """Retorna um filme completo, carregando relações sem consultas N+1."""

        filme = await self._session.scalar(
            select(DimMovie).where(DimMovie.id_filme == filme_id).options(*DETALHE_LOAD_OPTIONS)
        )
        if filme is None:
            raise FilmeNaoEncontradoError
        return GestaoFilmesService._para_detalhe(filme)

    async def obter_trailer(self, filme_id: str) -> TrailerFilme:
        """Obtém e guarda o trailer oficial quando o catálogo ainda não o possui."""

        filme = await self._session.scalar(select(DimMovie).where(DimMovie.id_filme == filme_id))
        if filme is None:
            raise FilmeNaoEncontradoError
        if filme.url_trailer:
            return TrailerFilme(url_trailer=filme.url_trailer)

        gateway = TmdbGateway(get_settings().tmdb_api_token)
        try:
            if filme.id_filme.isdecimal():
                # IDs da seed são IDs TMDB: consultar diretamente evita anexar o
                # trailer de uma obra homônima encontrada pela pesquisa textual.
                trailer = (await gateway.obter(int(filme.id_filme))).url_trailer
            else:
                # Filmes locais não têm ID TMDB; só aceitamos uma correspondência
                # exata de título e ano, sem cair silenciosamente no primeiro resultado.
                resultados = await gateway.buscar(filme.titulo, filme.ano_lancamento)
                correspondencia = next(
                    (
                        item
                        for item in resultados
                        if item.titulo.casefold() == filme.titulo.casefold()
                        and (
                            filme.ano_lancamento is None
                            or item.ano_lancamento == filme.ano_lancamento
                        )
                    ),
                    None,
                )
                if correspondencia is None:
                    return TrailerFilme()
                trailer = (await gateway.obter(correspondencia.id)).url_trailer
        except FonteExternaIndisponivelError:
            return TrailerFilme()
        if not trailer:
            return TrailerFilme()

        filme.url_trailer = trailer
        try:
            await self._session.commit()
        except SQLAlchemyError:
            await self._session.rollback()
            logger.exception("Não foi possível salvar o trailer do filme %s", filme_id)
        return TrailerFilme(url_trailer=trailer)

    @staticmethod
    def _escapar_like(valor: str) -> str:
        return valor.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @classmethod
    def _ids_busca(cls, termo, tabela, coluna_id, fallback_id, fallback_texto):
        """Uses the trigram index for substrings; short searches retain LIKE semantics."""
        if len(termo) >= 3:
            frase = '"' + termo.replace('"', '""') + '"'
            tabela_base = tabela.removesuffix("_search")
            parametro = f"termo_fts_{tabela}"
            return (
                select(text(f"{tabela_base}.{coluna_id}"))
                .select_from(
                    text(
                        f"{tabela_base} JOIN {tabela} "
                        f"ON {tabela_base}.rowid = {tabela}.rowid"
                    )
                )
                .where(text(f"{tabela} MATCH :{parametro}"))
                .params(**{parametro: frase})
            )

        escaped = cls._escapar_like(termo.casefold())
        return select(fallback_id).where(
            func.lower(fallback_texto).like(f"%{escaped}%", escape="\\")
        )

    @staticmethod
    def _para_resumo(filme: DimMovie) -> FilmeResumo:
        resumo = filme.reviews_summary
        return FilmeResumo(
            id=filme.id_filme,
            titulo=filme.titulo,
            ano_lancamento=filme.ano_lancamento,
            url_poster=filme.url_poster,
            url_backdrop=filme.url_backdrop,
            generos=[
                GeneroResumo(id=genero.sk_genre_id, nome=genero.nome_genero)
                for genero in filme.genres
            ],
            nota_media=resumo.nota_media_usuarios if resumo else None,
            quantidade_avaliacoes=resumo.qtd_avaliacoes_usuarios if resumo else 0,
        )


class AvaliacoesService:
    """Coordena o histórico e o resumo público de avaliações de filmes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def listar(self, filme_id: str) -> list[AvaliacaoLeitura]:
        """Retorna o histórico em ordem cronológica reversa e determinística."""

        await self._obter_filme(filme_id)
        avaliacoes = await self._session.scalars(
            select(MovieReview)
            .join(MovieReview.movie)
            .where(DimMovie.id_filme == filme_id, MovieReview.visibilidade == "publica")
            .order_by(MovieReview.created_at.desc(), MovieReview.sk_movie_review_id.desc())
        )
        return [self._para_leitura(avaliacao) for avaliacao in avaliacoes]

    async def obter_do_usuario(self, filme_id: str, usuario: User) -> AvaliacaoLeitura | None:
        """Retorna a avaliação privada ou pública do usuário para preencher a edição."""

        await self._obter_filme(filme_id)
        avaliacao = await self._session.scalar(
            select(MovieReview)
            .join(MovieReview.movie)
            .where(DimMovie.id_filme == filme_id, MovieReview.user_id == usuario.id)
            .order_by(MovieReview.created_at.desc(), MovieReview.sk_movie_review_id.desc())
            .limit(1)
        )
        return self._para_leitura(avaliacao) if avaliacao else None

    async def criar(
        self,
        filme_id: str,
        dados: AvaliacaoCriacao,
        usuario: User,
    ) -> AvaliacaoLeitura:
        """Insere uma avaliação e atualiza seu agregado na mesma transação."""

        filme = await self._obter_filme(filme_id)
        try:
            resumo = filme.reviews_summary
            avaliacao = await self._session.scalar(
                select(MovieReview)
                .where(
                    MovieReview.sk_movie_id == filme.sk_movie_id,
                    MovieReview.user_id == usuario.id,
                )
                .order_by(MovieReview.created_at.desc(), MovieReview.sk_movie_review_id.desc())
                .limit(1)
            )
            if avaliacao is None:
                avaliacao = MovieReview(
                    sk_movie_id=filme.sk_movie_id,
                    user_id=usuario.id,
                    nome=usuario.nome,
                    nota=dados.nota,
                    comentario=dados.comentario,
                    visibilidade=dados.visibilidade,
                )
                self._session.add(avaliacao)
                await self._session.flush()
                if resumo is None:
                    resumo = DimReview(
                        sk_movie_id=filme.sk_movie_id,
                        qtd_avaliacoes_usuarios=1,
                        nota_media_usuarios=dados.nota,
                    )
                    self._session.add(resumo)
                else:
                    quantidade_anterior = resumo.qtd_avaliacoes_usuarios
                    media_anterior = resumo.nota_media_usuarios or 0
                    resumo.nota_media_usuarios = (
                        (media_anterior * quantidade_anterior) + dados.nota
                    ) / (quantidade_anterior + 1)
                    resumo.qtd_avaliacoes_usuarios = quantidade_anterior + 1
            else:
                nota_anterior = avaliacao.nota
                avaliacao.nome = usuario.nome
                avaliacao.nota = dados.nota
                avaliacao.comentario = dados.comentario
                avaliacao.visibilidade = dados.visibilidade
                if resumo is not None and resumo.qtd_avaliacoes_usuarios:
                    media_anterior = resumo.nota_media_usuarios or 0
                    resumo.nota_media_usuarios = (
                        (media_anterior * resumo.qtd_avaliacoes_usuarios)
                        - nota_anterior
                        + dados.nota
                    ) / resumo.qtd_avaliacoes_usuarios

            await self._session.commit()
            await self._session.refresh(avaliacao)
        except IntegrityError as error:
            await self._session.rollback()
            logger.warning("Cadastro de avaliação interrompido por conflito de integridade.")
            raise FilmeConflitoError from error
        except SQLAlchemyError as error:
            await self._session.rollback()
            logger.error("Cadastro de avaliação interrompido por falha de persistência.")
            raise FilmePersistenceError from error

        return self._para_leitura(avaliacao)

    async def remover_do_usuario(self, filme_id: str, usuario: User) -> None:
        """Remove somente a avaliação da conta atual e recompõe a média do filme."""

        filme = await self._obter_filme(filme_id)
        avaliacao = await self._session.scalar(
            select(MovieReview)
            .where(
                MovieReview.sk_movie_id == filme.sk_movie_id,
                MovieReview.user_id == usuario.id,
            )
            .order_by(MovieReview.created_at.desc(), MovieReview.sk_movie_review_id.desc())
            .limit(1)
        )
        if avaliacao is None:
            return

        try:
            resumo = filme.reviews_summary
            if resumo is not None and resumo.qtd_avaliacoes_usuarios <= 1:
                await self._session.delete(resumo)
            elif resumo is not None:
                quantidade_anterior = resumo.qtd_avaliacoes_usuarios
                media_anterior = resumo.nota_media_usuarios or 0
                resumo.qtd_avaliacoes_usuarios = quantidade_anterior - 1
                resumo.nota_media_usuarios = (
                    (media_anterior * quantidade_anterior) - avaliacao.nota
                ) / resumo.qtd_avaliacoes_usuarios
            await self._session.delete(avaliacao)
            await self._session.commit()
        except SQLAlchemyError as error:
            await self._session.rollback()
            logger.error("Remoção de avaliação interrompida por falha de persistência.")
            raise FilmePersistenceError from error

    async def _obter_filme(self, filme_id: str) -> DimMovie:
        filme = await self._session.scalar(
            select(DimMovie)
            .where(DimMovie.id_filme == filme_id)
            .options(selectinload(DimMovie.reviews_summary))
        )
        if filme is None:
            raise FilmeNaoEncontradoError
        return filme

    @staticmethod
    def _para_leitura(avaliacao: MovieReview) -> AvaliacaoLeitura:
        return AvaliacaoLeitura(
            id=avaliacao.sk_movie_review_id,
            nome=avaliacao.nome,
            nota=avaliacao.nota,
            comentario=avaliacao.comentario,
            visibilidade=avaliacao.visibilidade,
            criada_em=avaliacao.created_at,
        )


class GestaoFilmesService:
    """Coordena escritas atômicas do catálogo de filmes."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def criar(self, dados: FilmeCriacao) -> FilmeDetalhe:
        """Cria um filme e reutiliza dimensões já cadastradas quando possível."""

        try:
            generos = await self._obter_ou_criar_generos(dados.generos)
            diretor = await self._obter_ou_criar_pessoa(dados.diretor, "Diretor")
            atores = await self._obter_ou_criar_pessoas(dados.atores, "Ator")
            roteiristas = await self._obter_ou_criar_pessoas(dados.roteiristas, "Roteirista")
            produtoras = await self._obter_ou_criar_produtoras(dados.produtoras)

            filme = DimMovie(
                id_filme=f"local-{uuid4().hex}",
                titulo=dados.titulo,
                data_lancamento=dados.data_lancamento,
                ano_lancamento=dados.ano_lancamento,
                duracao_minutos=dados.duracao_minutos,
                status_filme=dados.status_filme,
                sinopse=dados.sinopse,
                url_poster=dados.url_poster,
                url_backdrop=dados.url_backdrop,
                url_trailer=dados.url_trailer,
                genres=generos,
                people=[diretor, *atores, *roteiristas],
                companies=produtoras,
            )
            self._session.add(filme)
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            logger.warning("Cadastro de filme interrompido por conflito de integridade.")
            raise FilmeConflitoError from error
        except SQLAlchemyError as error:
            await self._session.rollback()
            logger.error("Cadastro de filme interrompido por falha de persistência.")
            raise FilmePersistenceError from error

        return await CatalogoFilmesService(self._session).obter_detalhe(filme.id_filme)

    async def atualizar(self, filme_id: str, dados: FilmeAtualizacao) -> FilmeDetalhe:
        """Atualiza somente os campos enviados, incluindo relações quando necessário."""

        filme = await self._obter_filme_para_escrita(filme_id)
        try:
            for campo in (
                "titulo",
                "ano_lancamento",
                "sinopse",
                "data_lancamento",
                "duracao_minutos",
                "status_filme",
                "url_poster",
                "url_backdrop",
                "url_trailer",
            ):
                if campo in dados.model_fields_set:
                    setattr(filme, campo, getattr(dados, campo))

            if "generos" in dados.model_fields_set:
                filme.genres = await self._obter_ou_criar_generos(dados.generos or [])
            if "diretor" in dados.model_fields_set:
                diretor = await self._obter_ou_criar_pessoa(dados.diretor or "", "Diretor")
                self._substituir_pessoas_por_papel(filme, "Diretor", [diretor])
            if "atores" in dados.model_fields_set:
                atores = await self._obter_ou_criar_pessoas(dados.atores or [], "Ator")
                self._substituir_pessoas_por_papel(filme, "Ator", atores)
            if "roteiristas" in dados.model_fields_set:
                roteiristas = await self._obter_ou_criar_pessoas(
                    dados.roteiristas or [], "Roteirista"
                )
                self._substituir_pessoas_por_papel(filme, "Roteirista", roteiristas)
            if "produtoras" in dados.model_fields_set:
                filme.companies = await self._obter_ou_criar_produtoras(dados.produtoras or [])

            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            logger.warning("Atualização de filme interrompida por conflito de integridade.")
            raise FilmeConflitoError from error
        except SQLAlchemyError as error:
            await self._session.rollback()
            logger.error("Atualização de filme interrompida por falha de persistência.")
            raise FilmePersistenceError from error

        return await CatalogoFilmesService(self._session).obter_detalhe(filme.id_filme)

    async def remover(self, filme_id: str) -> None:
        """Remove um filme e seus relacionamentos dependentes de forma atômica."""

        filme = await self._obter_filme_para_escrita(filme_id)
        try:
            await self._session.delete(filme)
            await self._session.commit()
        except IntegrityError as error:
            await self._session.rollback()
            logger.warning("Remoção de filme interrompida por conflito de integridade.")
            raise FilmeConflitoError from error
        except SQLAlchemyError as error:
            await self._session.rollback()
            logger.error("Remoção de filme interrompida por falha de persistência.")
            raise FilmePersistenceError from error

    async def _obter_filme_para_escrita(self, filme_id: str) -> DimMovie:
        filme = await self._session.scalar(
            select(DimMovie).where(DimMovie.id_filme == filme_id).options(*DETALHE_LOAD_OPTIONS)
        )
        if filme is None:
            raise FilmeNaoEncontradoError
        return filme

    @staticmethod
    def _substituir_pessoas_por_papel(
        filme: DimMovie, papel: PersonType, pessoas: list[DimPerson]
    ) -> None:
        filme.people = [pessoa for pessoa in filme.people if pessoa.tipo_pessoa != papel] + pessoas

    async def _obter_ou_criar_generos(self, nomes: list[str]) -> list[DimGenre]:
        generos: list[DimGenre] = []
        for nome in nomes:
            genero = await self._session.scalar(
                select(DimGenre).where(func.lower(DimGenre.nome_genero) == nome.lower())
            )
            generos.append(genero or DimGenre(nome_genero=nome))
        return sorted(generos, key=lambda genero: genero.nome_genero.casefold())

    async def _obter_ou_criar_pessoa(self, nome: str, papel: PersonType) -> DimPerson:
        pessoa = await self._session.scalar(
            select(DimPerson).where(
                func.lower(DimPerson.nome_pessoa) == nome.lower(),
                DimPerson.tipo_pessoa == papel,
            )
        )
        return pessoa or DimPerson(nome_pessoa=nome, tipo_pessoa=papel)

    async def _obter_ou_criar_pessoas(self, nomes: list[str], papel: PersonType) -> list[DimPerson]:
        pessoas = [await self._obter_ou_criar_pessoa(nome, papel) for nome in nomes]
        return sorted(pessoas, key=lambda pessoa: pessoa.nome_pessoa.casefold())

    async def _obter_ou_criar_produtoras(self, nomes: list[str]) -> list[DimCompany]:
        produtoras: list[DimCompany] = []
        for nome in nomes:
            produtora = await self._session.scalar(
                select(DimCompany).where(func.lower(DimCompany.nome_produtora) == nome.lower())
            )
            produtoras.append(produtora or DimCompany(nome_produtora=nome))
        return sorted(produtoras, key=lambda produtora: produtora.nome_produtora.casefold())

    @staticmethod
    def _para_detalhe(filme: DimMovie) -> FilmeDetalhe:
        resumo = filme.reviews_summary
        desempenho = filme.performance
        return FilmeDetalhe(
            id=filme.id_filme,
            titulo=filme.titulo,
            ano_lancamento=filme.ano_lancamento,
            url_poster=filme.url_poster,
            generos=[
                GeneroResumo(id=genero.sk_genre_id, nome=genero.nome_genero)
                for genero in filme.genres
            ],
            nota_media=resumo.nota_media_usuarios if resumo else None,
            quantidade_avaliacoes=resumo.qtd_avaliacoes_usuarios if resumo else 0,
            data_lancamento=filme.data_lancamento,
            duracao_minutos=filme.duracao_minutos,
            status_filme=filme.status_filme,
            sinopse=filme.sinopse,
            url_backdrop=filme.url_backdrop,
            url_trailer=filme.url_trailer,
            pessoas=[
                PessoaResumo(
                    id=pessoa.sk_person_id, nome=pessoa.nome_pessoa, papel=pessoa.tipo_pessoa
                )
                for pessoa in sorted(
                    filme.people,
                    key=lambda pessoa: (pessoa.tipo_pessoa, pessoa.nome_pessoa.casefold()),
                )
            ],
            produtoras=[
                ProdutoraResumo(id=produtora.sk_company_id, nome=produtora.nome_produtora)
                for produtora in filme.companies
            ],
            desempenho=(
                DesempenhoFilme(
                    orcamento_usd=float(desempenho.orcamento_usd)
                    if desempenho.orcamento_usd is not None
                    else None,
                    receita_usd=float(desempenho.receita_usd)
                    if desempenho.receita_usd is not None
                    else None,
                    lucro_usd=float(desempenho.lucro_usd),
                    orcamento_brl=float(desempenho.orcamento_brl)
                    if desempenho.orcamento_brl is not None
                    else None,
                    receita_brl=float(desempenho.receita_brl)
                    if desempenho.receita_brl is not None
                    else None,
                    lucro_brl=float(desempenho.lucro_brl),
                    popularidade=desempenho.popularidade,
                    nota_tmdb=desempenho.nota_tmdb,
                    quantidade_tmdb=desempenho.qtd_tmdb,
                    nota_imdb=desempenho.nota_imdb,
                    quantidade_imdb=desempenho.qtd_imdb,
                )
                if desempenho
                else None
            ),
            avaliacoes=[
                AvaliacaoLeitura(
                    id=avaliacao.sk_movie_review_id,
                    nome=avaliacao.nome,
                    nota=avaliacao.nota,
                    comentario=avaliacao.comentario,
                    visibilidade=avaliacao.visibilidade,
                    criada_em=avaliacao.created_at,
                )
                for avaliacao in filme.reviews
                if avaliacao.visibilidade == "publica"
            ],
        )
