"""Tests for the SamizdatIndex type and matview unique-index sidekick."""

import pytest

from dbsamizdat.samizdat import (
    SamizdatIndex,
    SamizdatMaterializedView,
    SamizdatTable,
    sd_is_index,
)
from dbsamizdat.samtypes import FQTuple, entitypes


class Pet(SamizdatTable):
    sql_template = "${preamble} (id SERIAL PRIMARY KEY, name TEXT) ${postamble}"


class PetNameIdx(SamizdatIndex):
    on_table = Pet
    sql_template = "${preamble} (name);"


class PetUniqueLowerNameIdx(SamizdatIndex):
    on_table = Pet
    unique = True
    sql_template = "${preamble} (lower(name)) WHERE name IS NOT NULL;"


class PetGinNameIdx(SamizdatIndex):
    on_table = Pet
    method = "gin"
    sql_template = "${preamble} (name gin_trgm_ops);"


@pytest.mark.unit
def test_index_basic_properties():
    assert PetNameIdx.entity_type == entitypes.INDEX
    assert PetNameIdx.get_name() == "PetNameIdx"
    assert PetNameIdx.fq() == FQTuple("public", "PetNameIdx")
    assert sd_is_index(PetNameIdx)
    assert not sd_is_index(Pet)


@pytest.mark.unit
def test_index_create_sql_shape():
    sql = PetNameIdx.create()
    assert "CREATE INDEX" in sql
    assert "UNIQUE" not in sql
    # bare unqualified index name, schema-qualified target table
    assert '"PetNameIdx"' in sql
    assert 'ON "public"."Pet"' in sql
    assert "USING btree" in sql
    # template body is appended
    assert "(name)" in sql


@pytest.mark.unit
def test_index_unique_and_where():
    sql = PetUniqueLowerNameIdx.create()
    assert "CREATE UNIQUE INDEX" in sql
    assert "lower(name)" in sql
    assert "WHERE name IS NOT NULL" in sql


@pytest.mark.unit
def test_index_method_override():
    sql = PetGinNameIdx.create()
    assert "USING gin" in sql


@pytest.mark.unit
def test_index_drop_sql():
    sql = PetNameIdx.drop(if_exists=True)
    assert sql.startswith("DROP INDEX")
    assert "IF EXISTS" in sql
    # schema-qualified for DROP (unlike CREATE)
    assert '"public"."PetNameIdx"' in sql
    assert "CASCADE" in sql


@pytest.mark.unit
def test_index_schema_follows_table():
    class OtherTable(SamizdatTable):
        schema = "analytics"
        sql_template = "${preamble} (id INTEGER) ${postamble}"

    class OtherIdx(SamizdatIndex):
        on_table = OtherTable
        sql_template = "${preamble} (id);"

    # Index lives in the table's schema, not its own default.
    assert OtherIdx.fq().schema == "analytics"
    assert 'ON "analytics"."OtherTable"' in OtherIdx.create()


@pytest.mark.unit
def test_index_includes_table_in_unmanaged_deps():
    # The on_table reference is always treated as an unmanaged dep,
    # matching the SamizdatTrigger convention.
    assert Pet.fq() in PetNameIdx.fqdeps_on_unmanaged()


@pytest.mark.unit
def test_index_definition_hash_stable():
    assert PetNameIdx.definition_hash() == PetNameIdx.definition_hash()
    assert PetNameIdx.definition_hash() != PetUniqueLowerNameIdx.definition_hash()


@pytest.mark.unit
def test_index_head_id_distinguishes_tables():
    class OtherPet(SamizdatTable):
        sql_template = "${preamble} (id INTEGER) ${postamble}"

    class IdxOnPet(SamizdatIndex):
        on_table = Pet
        sql_template = "${preamble} (id);"

    class IdxOnOther(SamizdatIndex):
        on_table = OtherPet
        sql_template = "${preamble} (id);"

    assert IdxOnPet.head_id() != IdxOnOther.head_id()


@pytest.mark.unit
def test_matview_emits_unique_index_when_concurrent():
    class MV(SamizdatMaterializedView):
        refresh_concurrently = True
        refresh_unique_columns = ("id",)
        sql_template = "${preamble} SELECT 1 AS id ${postamble}"

    sidekicks = list(MV.sidekicks())
    indexes = [sk for sk in sidekicks if sd_is_index(sk)]
    assert len(indexes) == 1
    idx = indexes[0]
    assert idx.unique is True
    assert idx.on_table is MV
    create_sql = idx.create()
    assert "CREATE UNIQUE INDEX" in create_sql
    assert '("id")' in create_sql


@pytest.mark.unit
def test_matview_no_unique_index_without_columns():
    class MV(SamizdatMaterializedView):
        refresh_concurrently = True
        sql_template = "${preamble} SELECT 1 ${postamble}"

    assert not any(sd_is_index(sk) for sk in MV.sidekicks())


@pytest.mark.unit
def test_matview_no_unique_index_without_concurrent_flag():
    class MV(SamizdatMaterializedView):
        refresh_unique_columns = ("id",)
        sql_template = "${preamble} SELECT 1 AS id ${postamble}"

    assert not any(sd_is_index(sk) for sk in MV.sidekicks())
