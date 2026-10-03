"""Motor leve e explicável de recomendações por similaridade de conteúdo."""

import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from heapq import nsmallest
from math import log1p, sqrt

from sqlalchemy import (
    Integer,
    String,
    case,
    column,
    func,
    literal,
    or_,
    select,
    table,
    text,
    union_all,
)
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.movies.models import (
    DimMovie,
    MovieReview,
    bridge_movie_genre,
    bridge_movie_person,
)
from app.taste_map.schemas import ArestaMapaGostos, MapaGostos, NoMapaGostos
from app.users.models import User

PALAVRAS_SEM_SINAL = frozenset(
    {
        "a",
        "ao",
        "aos",
        "as",
        "com",
        "como",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "entre",
        "essa",
        "esse",
        "esta",
        "este",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "para",
        "por",
        "que",
        "se",
        "sua",
        "são",
        "tem",
        "uma",
        "um",
    }
)
LIMITE_CANDIDATOS_MINIMO = 350
LIMITE_CANDIDATOS_MAXIMO = 700
LIMITE_TERMOS_SINOPSE = 32


@dataclass(frozen=True, slots=True)
class PesosSimilaridade:
    """Pesos do KNN; podem ser trocados ao instanciar o serviço."""

    generos: float = 0.34
    direcao: float = 0.18
    elenco: float = 0.10
    sinopse: float = 0.18
    ano: float = 0.08
    metricas: float = 0.12

    def normalizados(self) -> dict[str, float]:
        valores = {
            "generos": self.generos,
            "direcao": self.direcao,
            "elenco": self.elenco,
            "sinopse": self.sinopse,
            "ano": self.ano,
            "metricas": self.metricas,
        }
        if any(valor < 0 for valor in valores.values()) or not any(valores.values()):
            raise ValueError(
                "Os pesos de similaridade devem ser positivos e ter alguma relevância."
            )
        total = sum(valores.values())
        return {chave: valor / total for chave, valor in valores.items()}


@dataclass(frozen=True, slots=True)
class VetorFilme:
    """Representação calculada uma vez e reutilizada em todas as comparações."""

    generos: frozenset[str]
    diretores: frozenset[str]
    elenco: frozenset[str]
    sinopse: frozenset[str]
    ano: int | None
    nota_externa: float | None
    popularidade: float | None


class MapaGostosService:
    """Monta um subgrafo pequeno a partir dos filmes avaliados pelo usuário.

    Não há treino nem dado externo escondido: cada sugestão vem de gêneros,
    pessoas, sinopse, época e métricas já presentes no catálogo. Isso torna o
    resultado fácil de explicar e mantém o custo previsível para a atividade.
    """

    def __init__(self, session: AsyncSession, pesos: PesosSimilaridade | None = None):
        self._session = session
        self._pesos = (pesos or PesosSimilaridade()).normalizados()

    async def obter(
        self,
        usuario: User,
        *,
        limite_nos: int,
        vizinhos_por_filme: int,
        busca: str | None = None,
        excluir: set[str] | None = None,
    ) -> MapaGostos:
        ids_avaliados = set(
            await self._session.scalars(
                select(MovieReview.sk_movie_id).where(MovieReview.user_id == usuario.id)
            )
        )
        total_avaliados = len(ids_avaliados)
        if not ids_avaliados:
            return MapaGostos(
                nos=[],
                arestas=[],
                total_avaliados=0,
                limite_nos=limite_nos,
                vizinhos_por_filme=vizinhos_por_filme,
            )

        # Prioriza o que a pessoa mais gostou e ainda deixa espaço para descobrir.
        max_avaliadas = max(1, limite_nos // 2)
        avaliadas = self._avaliadas_distintas(
            await self._avaliacoes_do_usuario(usuario.id, limit=max_avaliadas)
        )
        filmes_origem = [avaliacao.movie for avaliacao in avaliadas if avaliacao.movie is not None]
        candidatos = await self._catalogo_candidato(
            filmes_origem,
            ids_avaliados,
            excluir or set(),
            limite_candidatos=self._limite_candidatos(limite_nos - len(avaliadas)),
        )
        recomendacoes, arestas = self._construir_conexoes(
            avaliadas,
            candidatos,
            limite_recomendacoes=max(0, limite_nos - len(avaliadas)),
            vizinhos_por_filme=vizinhos_por_filme,
        )
        nos = [self._no_avaliado(avaliacao) for avaliacao in avaliadas]
        nos.extend(self._no_recomendado(filme, afinidade) for filme, afinidade in recomendacoes)

        if busca and busca.strip():
            nos, arestas = self._filtrar_busca(nos, arestas, busca)

        return MapaGostos(
            nos=nos,
            arestas=arestas,
            total_avaliados=total_avaliados,
            limite_nos=limite_nos,
            vizinhos_por_filme=vizinhos_por_filme,
        )

    @staticmethod
    def _limite_candidatos(limite_recomendacoes: int) -> int:
        """Mantém candidatos suficientes sem hidratar milhares de filmes para um mapa curto."""

        return min(
            LIMITE_CANDIDATOS_MAXIMO,
            max(LIMITE_CANDIDATOS_MINIMO, limite_recomendacoes * 35),
        )

    async def _avaliacoes_do_usuario(self, user_id: str, *, limit: int) -> list[MovieReview]:
        resultado = await self._session.execute(
            select(MovieReview)
            .where(MovieReview.user_id == user_id)
            .options(
                selectinload(MovieReview.movie).selectinload(DimMovie.genres),
                selectinload(MovieReview.movie).selectinload(DimMovie.people),
                selectinload(MovieReview.movie).selectinload(DimMovie.performance),
            )
            .order_by(MovieReview.nota.desc(), MovieReview.created_at.desc())
            .limit(limit)
        )
        return list(resultado.scalars())

    async def _catalogo_candidato(
        self,
        filmes_origem: list[DimMovie],
        ids_avaliados: set[str],
        excluir: set[str],
        *,
        limite_candidatos: int,
    ) -> list[DimMovie]:
        """Busca uma amostra ampla por sinais no SQL antes de carregar relações.

        O catálogo inteiro não é hidratado no ORM: gêneros, pessoas e termos de
        sinopse geram uma pontuação preliminar no banco. A similaridade completa
        e explicável continua sendo calculada em Python para uma amostra proporcional
        ao número de recomendações que o mapa precisa exibir.
        """

        generos_origem = {genero.sk_genre_id for filme in filmes_origem for genero in filme.genres}
        pessoas_origem = {pessoa.sk_person_id for filme in filmes_origem for pessoa in filme.people}
        termos_origem = Counter(
            termo for filme in filmes_origem for termo in self._vetor_sinopse(filme.sinopse)
        )
        termos_sinopse = [
            termo
            for termo, _ in sorted(
                termos_origem.items(),
                key=lambda item: (item[1], -len(item[0]), item[0]),
            )[:LIMITE_TERMOS_SINOPSE]
        ]
        sinais = []

        if generos_origem:
            genero_scores = (
                select(
                    bridge_movie_genre.c.sk_movie_id.label("movie_id"),
                    (func.count() * 3).label("score"),
                )
                .where(bridge_movie_genre.c.sk_genre_id.in_(generos_origem))
                .group_by(bridge_movie_genre.c.sk_movie_id)
                .order_by(func.count().desc())
                .limit(limite_candidatos)
                .subquery()
            )
            sinais.append(
                select(genero_scores.c.movie_id, genero_scores.c.score)
            )
        if pessoas_origem:
            pessoa_scores = (
                select(
                    bridge_movie_person.c.sk_movie_id.label("movie_id"),
                    (func.count() * 4).label("score"),
                )
                .where(bridge_movie_person.c.sk_person_id.in_(pessoas_origem))
                .group_by(bridge_movie_person.c.sk_movie_id)
                .order_by(func.count().desc())
                .limit(limite_candidatos)
                .subquery()
            )
            sinais.append(
                select(pessoa_scores.c.movie_id, pessoa_scores.c.score)
            )
        if termos_sinopse:
            consulta_fts = " OR ".join(f'"{termo}"' for termo in termos_sinopse)
            indice_sinopse = table(
                "movie_synopsis_fts",
                column("sk_movie_id", String),
                column("sinopse", String),
            )
            busca_texto = (
                select(
                    indice_sinopse.c.sk_movie_id.label("movie_id"),
                    literal(6, type_=Integer).label("score"),
                )
                .where(text("movie_synopsis_fts MATCH :consulta_fts"))
                .order_by(text("bm25(movie_synopsis_fts)"))
                .limit(limite_candidatos)
                .params(consulta_fts=consulta_fts)
                .subquery()
            )
            sinais.append(select(busca_texto.c.movie_id, busca_texto.c.score))

        if not sinais:
            return []

        pontuacoes = union_all(*sinais).subquery()
        ranking = (
            select(
                pontuacoes.c.movie_id,
                func.sum(pontuacoes.c.score).label("score"),
            )
            .join(DimMovie, DimMovie.sk_movie_id == pontuacoes.c.movie_id)
            .where(DimMovie.sk_movie_id.not_in(ids_avaliados))
            .where(DimMovie.id_filme.not_in(excluir))
            .group_by(pontuacoes.c.movie_id)
            .order_by(func.sum(pontuacoes.c.score).desc(), DimMovie.titulo, DimMovie.sk_movie_id)
            .limit(limite_candidatos)
            .subquery()
        )
        try:
            ids_resultado = await self._session.scalars(select(ranking.c.movie_id))
            ids_candidatos = list(ids_resultado)
        except OperationalError as error:
            # Testes e bancos locais ainda em migração podem não ter o índice.
            if "no such table: movie_synopsis_fts" not in str(error).casefold():
                raise
            ids_candidatos = await self._catalogo_candidato_sem_fts(
                filmes_origem,
                ids_avaliados,
                excluir,
                generos_origem,
                pessoas_origem,
                limite_candidatos=limite_candidatos,
            )
        if not ids_candidatos:
            return []

        resultado = await self._session.execute(
            select(DimMovie)
            .where(DimMovie.sk_movie_id.in_(ids_candidatos))
            .options(
                selectinload(DimMovie.genres),
                selectinload(DimMovie.people),
                selectinload(DimMovie.performance),
            )
        )
        return list(resultado.scalars().unique())

    async def _catalogo_candidato_sem_fts(
        self,
        filmes_origem: list[DimMovie],
        ids_avaliados: set[str],
        excluir: set[str],
        generos_origem: set[str],
        pessoas_origem: set[str],
        *,
        limite_candidatos: int,
    ) -> list[str]:
        """Fallback para bancos de teste ainda sem a migration FTS5."""

        sinais = []
        if generos_origem:
            genero_scores = (
                select(
                    bridge_movie_genre.c.sk_movie_id.label("movie_id"),
                    (func.count() * 3).label("score"),
                )
                .where(bridge_movie_genre.c.sk_genre_id.in_(generos_origem))
                .group_by(bridge_movie_genre.c.sk_movie_id)
                .order_by(func.count().desc())
                .limit(limite_candidatos)
                .subquery()
            )
            sinais.append(
                select(genero_scores.c.movie_id, genero_scores.c.score)
            )
        if pessoas_origem:
            pessoa_scores = (
                select(
                    bridge_movie_person.c.sk_movie_id.label("movie_id"),
                    (func.count() * 4).label("score"),
                )
                .where(bridge_movie_person.c.sk_person_id.in_(pessoas_origem))
                .group_by(bridge_movie_person.c.sk_movie_id)
                .order_by(func.count().desc())
                .limit(limite_candidatos)
                .subquery()
            )
            sinais.append(
                select(pessoa_scores.c.movie_id, pessoa_scores.c.score)
            )
        termos = sorted(
            {termo for filme in filmes_origem for termo in self._vetor_sinopse(filme.sinopse)}
        )[:LIMITE_TERMOS_SINOPSE]
        if termos:
            correspondencias = [DimMovie.sinopse.ilike(f"%{termo}%") for termo in termos]
            score = sum(case((condicao, 1), else_=0) for condicao in correspondencias)
            sinais.append(
                select(
                    DimMovie.sk_movie_id.label("movie_id"),
                    score.label("score"),
                ).where(or_(*correspondencias))
            )
        if not sinais:
            return []
        pontuacoes = union_all(*sinais).subquery()
        ranking = (
            select(pontuacoes.c.movie_id)
            .join(DimMovie, DimMovie.sk_movie_id == pontuacoes.c.movie_id)
            .where(DimMovie.sk_movie_id.not_in(ids_avaliados))
            .where(DimMovie.id_filme.not_in(excluir))
            .group_by(pontuacoes.c.movie_id)
            .order_by(func.sum(pontuacoes.c.score).desc(), DimMovie.titulo)
            .limit(limite_candidatos)
        )
        return list(await self._session.scalars(ranking))

    @staticmethod
    def _avaliadas_distintas(avaliacoes: Iterable[MovieReview]) -> list[MovieReview]:
        vistas: set[str] = set()
        distintas: list[MovieReview] = []
        for avaliacao in avaliacoes:
            if avaliacao.sk_movie_id in vistas:
                continue
            vistas.add(avaliacao.sk_movie_id)
            distintas.append(avaliacao)
        return distintas

    def _construir_conexoes(
        self,
        avaliadas: list[MovieReview],
        candidatos: list[DimMovie],
        *,
        limite_recomendacoes: int,
        vizinhos_por_filme: int,
    ) -> tuple[list[tuple[DimMovie, float]], list[ArestaMapaGostos]]:
        if not limite_recomendacoes:
            return [], []
        melhores: dict[str, tuple[DimMovie, float]] = {}
        arestas_por_par: dict[tuple[str, str], ArestaMapaGostos] = {}
        vetores_candidatos = {
            candidato.sk_movie_id: self._vetor(candidato) for candidato in candidatos
        }

        for avaliacao in avaliadas:
            filme_origem = avaliacao.movie
            if filme_origem is None:
                continue
            vetor_origem = self._vetor(filme_origem)
            proximos = nsmallest(
                vizinhos_por_filme,
                (
                    (
                        candidato,
                        self._afinidade_vetores(
                            vetor_origem,
                            vetores_candidatos[candidato.sk_movie_id],
                            avaliacao.nota,
                        ),
                    )
                    for candidato in candidatos
                ),
                key=lambda item: (-item[1], item[0].titulo.casefold()),
            )
            for candidato, afinidade in proximos:
                # A época sozinha é insuficiente para sugerir uma história;
                # é apenas um desempate quando já existe afinidade de conteúdo.
                if afinidade < 0.12:
                    continue
                atual = melhores.get(candidato.sk_movie_id)
                if atual is None or afinidade > atual[1]:
                    melhores[candidato.sk_movie_id] = (candidato, afinidade)
                arestas_por_par[(filme_origem.id_filme, candidato.id_filme)] = ArestaMapaGostos(
                    origem=filme_origem.id_filme,
                    destino=candidato.id_filme,
                    peso=round(afinidade, 3),
                    explicacao=self._explicacao(filme_origem, candidato),
                )

        recomendacoes = sorted(
            melhores.values(), key=lambda item: (-item[1], item[0].titulo.casefold())
        )[:limite_recomendacoes]
        ids_recomendados = {filme.id_filme for filme, _ in recomendacoes}
        arestas = [
            aresta for aresta in arestas_por_par.values() if aresta.destino in ids_recomendados
        ]
        return recomendacoes, sorted(arestas, key=lambda aresta: (-aresta.peso, aresta.origem))

    def _afinidade(self, origem: DimMovie, candidato: DimMovie, nota: float) -> float:
        return self._afinidade_vetores(self._vetor(origem), self._vetor(candidato), nota)

    def _afinidade_vetores(self, origem: VetorFilme, candidato: VetorFilme, nota: float) -> float:
        generos = len(origem.generos & candidato.generos) / max(
            1, len(origem.generos | candidato.generos)
        )
        direcao = 1.0 if origem.diretores & candidato.diretores else 0.0
        elenco = min(1.0, len(origem.elenco & candidato.elenco) / 2)
        sinopse = self._cosseno_binario(origem.sinopse, candidato.sinopse)
        anos = 0.0
        if origem.ano and candidato.ano:
            anos = max(0.0, 1 - abs(origem.ano - candidato.ano) / 30)
        metricas = self._similaridade_metricas_vetores(origem, candidato)
        # Ano e métricas refinam a recomendação, mas nunca bastam sem uma
        # ligação de conteúdo (gênero, pessoa ou termos da sinopse).
        if not (generos or direcao or elenco or sinopse):
            return 0.0
        afinidade = (
            self._pesos["generos"] * generos
            + self._pesos["direcao"] * direcao
            + self._pesos["elenco"] * elenco
            + self._pesos["sinopse"] * sinopse
            + self._pesos["ano"] * anos
            + self._pesos["metricas"] * metricas
        )
        sinal_da_avaliacao = 0.45 + max(0, min(nota, 10)) / 20
        return round(afinidade * sinal_da_avaliacao, 3)

    @classmethod
    def _vetor(cls, filme: DimMovie) -> VetorFilme:
        desempenho = filme.performance
        notas = (
            [nota for nota in (desempenho.nota_tmdb, desempenho.nota_imdb) if nota is not None]
            if desempenho
            else []
        )
        return VetorFilme(
            generos=frozenset(genero.nome_genero.casefold() for genero in filme.genres),
            diretores=frozenset(
                pessoa.nome_pessoa.casefold()
                for pessoa in filme.people
                if pessoa.tipo_pessoa == "Diretor"
            ),
            elenco=frozenset(
                pessoa.nome_pessoa.casefold()
                for pessoa in filme.people
                if pessoa.tipo_pessoa != "Diretor"
            ),
            sinopse=frozenset(cls._vetor_sinopse(filme.sinopse)),
            ano=filme.ano_lancamento,
            nota_externa=sum(notas) / len(notas) if notas else None,
            popularidade=(
                log1p(desempenho.popularidade)
                if desempenho and desempenho.popularidade is not None
                else None
            ),
        )

    @staticmethod
    def _vetor_sinopse(sinopse: str | None) -> set[str]:
        """Cria um vetor binário de termos relevantes para o cosseno textual."""

        return {
            termo
            for termo in re.findall(r"[\wÀ-ÿ]{3,}", (sinopse or "").casefold())
            if termo not in PALAVRAS_SEM_SINAL
        }

    @staticmethod
    def _cosseno_binario(origem: set[str], candidato: set[str]) -> float:
        if not origem or not candidato:
            return 0.0
        return len(origem & candidato) / sqrt(len(origem) * len(candidato))

    @staticmethod
    def _similaridade_metricas(origem: DimMovie, candidato: DimMovie) -> float:
        return MapaGostosService._similaridade_metricas_vetores(
            MapaGostosService._vetor(origem), MapaGostosService._vetor(candidato)
        )

    @staticmethod
    def _similaridade_metricas_vetores(origem: VetorFilme, candidato: VetorFilme) -> float:
        sinais: list[float] = []
        if origem.nota_externa is not None and candidato.nota_externa is not None:
            sinais.append(max(0.0, 1 - abs(origem.nota_externa - candidato.nota_externa) / 10))
        if origem.popularidade is not None and candidato.popularidade is not None:
            maior = max(origem.popularidade, candidato.popularidade, 1)
            sinais.append(1 - abs(origem.popularidade - candidato.popularidade) / maior)
        return sum(sinais) / len(sinais) if sinais else 0.0

    def _explicacao(self, origem: DimMovie, candidato: DimMovie) -> str:
        generos = sorted(
            {genero.nome_genero for genero in origem.genres}
            & {genero.nome_genero for genero in candidato.genres}
        )
        diretores = sorted(
            {pessoa.nome_pessoa for pessoa in origem.people if pessoa.tipo_pessoa == "Diretor"}
            & {pessoa.nome_pessoa for pessoa in candidato.people if pessoa.tipo_pessoa == "Diretor"}
        )
        pessoas = sorted(
            {pessoa.nome_pessoa for pessoa in origem.people}
            & {pessoa.nome_pessoa for pessoa in candidato.people}
        )
        termos = sorted(
            self._vetor_sinopse(origem.sinopse) & self._vetor_sinopse(candidato.sinopse)
        )
        partes: list[str] = []
        if generos:
            partes.append(f"gênero {generos[0]}")
        if diretores:
            partes.append(f"direção de {diretores[0]}")
        elif pessoas:
            partes.append(f"presença de {pessoas[0]}")
        if termos and len(partes) < 2:
            partes.append(f"tema {termos[0]}")
        if not partes and self._similaridade_metricas(origem, candidato):
            partes.append("métricas de recepção próximas")
        return "Conexão por " + " e ".join(partes) if partes else "Proximidade de época e estilo"

    @staticmethod
    def _generos(filme: DimMovie) -> list[str]:
        return [genero.nome_genero for genero in filme.genres]

    def _no_avaliado(self, avaliacao: MovieReview) -> NoMapaGostos:
        filme = avaliacao.movie
        assert filme is not None
        generos = self._generos(filme)
        return NoMapaGostos(
            id=filme.id_filme,
            titulo=filme.titulo,
            ano_lancamento=filme.ano_lancamento,
            url_poster=filme.url_poster,
            genero_principal=generos[0] if generos else None,
            generos=generos,
            nota_usuario=avaliacao.nota,
            tipo="avaliado",
        )

    def _no_recomendado(self, filme: DimMovie, afinidade: float) -> NoMapaGostos:
        generos = self._generos(filme)
        return NoMapaGostos(
            id=filme.id_filme,
            titulo=filme.titulo,
            ano_lancamento=filme.ano_lancamento,
            url_poster=filme.url_poster,
            genero_principal=generos[0] if generos else None,
            generos=generos,
            tipo="recomendado",
            afinidade=round(afinidade, 3),
        )

    @staticmethod
    def _filtrar_busca(
        nos: list[NoMapaGostos], arestas: list[ArestaMapaGostos], busca: str
    ) -> tuple[list[NoMapaGostos], list[ArestaMapaGostos]]:
        termo = busca.casefold().strip()
        encontrados = {no.id for no in nos if termo in no.titulo.casefold()}
        if not encontrados:
            return [], []
        adjacentes = {
            ponta
            for aresta in arestas
            for ponta in (aresta.origem, aresta.destino)
            if aresta.origem in encontrados or aresta.destino in encontrados
        }
        ids = encontrados | adjacentes
        return [no for no in nos if no.id in ids], [
            aresta for aresta in arestas if aresta.origem in ids and aresta.destino in ids
        ]
