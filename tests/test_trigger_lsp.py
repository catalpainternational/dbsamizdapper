"""
Tests for SamizdatTrigger behavior and LSP compliance.

These tests document current trigger behavior before refactoring
to fix the Liskov Substitution Principle violation.
"""

import pytest

from dbsamizdat.exceptions import DanglingReferenceError  # noqa: F401
from dbsamizdat.libgraph import sanity_check  # noqa: F401
from dbsamizdat.runner import cmd_sync, get_cursor
from dbsamizdat.samizdat import (
    SamizdatFunction,
    SamizdatMaterializedView,
    SamizdatTable,
    SamizdatTrigger,
)
from dbsamizdat.samtypes import entitypes  # noqa: F401

# ==================== Test Trigger Definitions ====================


class TestTable(SamizdatTable):
    """Table for trigger testing"""

    sql_template = """
        ${preamble}
        (
            id SERIAL PRIMARY KEY,
            value TEXT,
            updated_at TIMESTAMP DEFAULT NOW()
        )
        ${postamble}
    """


class UpdateTimestampFunction(SamizdatFunction):
    """Function for trigger to call"""

    function_arguments_signature = ""
    sql_template = """
        ${preamble}
        RETURNS trigger AS $THEBODY$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $THEBODY$ LANGUAGE plpgsql;
    """


class UpdateTimestampTrigger(SamizdatTrigger):
    """Trigger that calls the update timestamp function"""

    on_table = TestTable
    condition = "BEFORE UPDATE"
    deps_on = {UpdateTimestampFunction}
    sql_template = f"""
        ${{preamble}}
        FOR EACH ROW EXECUTE PROCEDURE {UpdateTimestampFunction.db_object_identity()};
    """


# ==================== Unit Tests - Current Behavior ====================


@pytest.mark.unit
def test_trigger_basic_properties():
    """Test basic properties of SamizdatTrigger - DOCUMENTS CURRENT BEHAVIOR"""
    assert UpdateTimestampTrigger.entity_type == entitypes.TRIGGER
    assert UpdateTimestampTrigger.get_name() == "UpdateTimestampTrigger"


@pytest.mark.unit
def test_trigger_schema_inherits_properly():
    """
    VERIFIES LSP FIX: Trigger.schema now properly inherits from parent.

    After fixing the LSP violation, triggers no longer force schema = None.
    Instead, they inherit the default "public" schema like other Samizdats,
    maintaining the parent class contract.
    """
    # Fixed behavior (LSP compliant)
    assert UpdateTimestampTrigger.schema == "public"

    # The actual schema used for the trigger is derived from the table in fq()
    fq = UpdateTimestampTrigger.fq()
    # The FQ now uses the table's schema properly
    assert fq.schema == TestTable.fq().schema


@pytest.mark.unit
def test_trigger_fq_identity():
    """
    VERIFIES LSP FIX: Trigger.fq() now returns FQTuple with proper semantics.

    The trigger's fq() now correctly uses the table's schema (not db_object_identity)
    and composes a unique object name that includes both trigger and table names.
    """
    fq = UpdateTimestampTrigger.fq()

    # Fixed behavior: schema is properly the table's schema
    assert fq.schema == "public"  # Correct schema, not full table identity
    assert fq.schema == TestTable.fq().schema

    # Object name now includes both trigger and table for uniqueness
    assert "UpdateTimestampTrigger" in fq.object_name
    assert "TestTable" in fq.object_name
    assert "__on__" in fq.object_name  # Separator showing relationship


@pytest.mark.unit
def test_trigger_on_table_dependency():
    """Test that triggers properly declare dependency on their table"""
    # Trigger should depend on its function
    assert UpdateTimestampFunction.fq() in UpdateTimestampTrigger.fqdeps_on()

    # Table should be in unmanaged deps
    assert TestTable.fq() in UpdateTimestampTrigger.fqdeps_on_unmanaged()


@pytest.mark.unit
def test_trigger_sql_generation():
    """Test SQL generation for triggers"""
    create_sql = UpdateTimestampTrigger.create()

    # Should contain CREATE TRIGGER
    assert "CREATE TRIGGER" in create_sql
    assert "UpdateTimestampTrigger" in create_sql
    assert "BEFORE UPDATE" in create_sql
    assert TestTable.db_object_identity() in create_sql

    # Test drop SQL
    drop_sql = UpdateTimestampTrigger.drop()
    assert "DROP TRIGGER" in drop_sql
    assert "UpdateTimestampTrigger" in drop_sql


@pytest.mark.unit
def test_trigger_str_representation():
    """Test string representation of trigger"""
    trigger_str = str(UpdateTimestampTrigger())

    # Should contain trigger name and table reference
    assert "UpdateTimestampTrigger" in trigger_str


@pytest.mark.unit
def test_trigger_definition_hash():
    """Test that triggers generate proper definition hashes"""
    hash1 = UpdateTimestampTrigger.definition_hash()
    hash2 = UpdateTimestampTrigger.definition_hash()

    # Should be consistent
    assert hash1 == hash2
    assert isinstance(hash1, str)
    assert len(hash1) == 32  # MD5 hash


@pytest.mark.unit
def test_trigger_head_id():
    """Test trigger head_id generation"""
    head_id = UpdateTimestampTrigger.head_id()

    # Should be an integer (hash)
    assert isinstance(head_id, int)

    # Should be consistent
    assert head_id == UpdateTimestampTrigger.head_id()


# ==================== Integration Tests ====================


@pytest.mark.integration
def test_trigger_creation(clean_db):
    """Test creating triggers in the database"""
    # Create table, function, and trigger
    cmd_sync(clean_db, [TestTable, UpdateTimestampFunction, UpdateTimestampTrigger])

    # Verify trigger exists
    with get_cursor(clean_db) as cursor:
        cursor.execute(
            """
            SELECT tgname, tgrelid::regclass::text
            FROM pg_trigger
            WHERE tgname = 'UpdateTimestampTrigger'
              AND tgisinternal = false
        """
        )
        result = cursor.fetchone()
        assert result is not None
        assert result[0] == "UpdateTimestampTrigger"


@pytest.mark.integration
@pytest.mark.slow
def test_trigger_functionality(clean_db):
    """Test that trigger can be created and basic operations work"""
    # Create table, function, and trigger
    cmd_sync(clean_db, [TestTable, UpdateTimestampFunction, UpdateTimestampTrigger])

    # Verify we can insert and update data (trigger will fire)
    with get_cursor(clean_db) as cursor:
        # Insert a row
        cursor.execute(
            f"""
            INSERT INTO {TestTable.db_object_identity()} (value)
            VALUES ('initial')
            RETURNING id
        """
        )
        initial_id = cursor.fetchone()[0]

        # Update the row - trigger will fire (updating timestamp)
        cursor.execute(
            f"""
            UPDATE {TestTable.db_object_identity()}
            SET value = 'updated'
            WHERE id = %s
        """,
            (initial_id,),
        )

        # Just verify the update worked (trigger fired without errors)
        cursor.execute(
            f"""
            SELECT value FROM {TestTable.db_object_identity()}
            WHERE id = %s
        """,
            (initial_id,),
        )
        result = cursor.fetchone()
        assert result[0] == "updated"


@pytest.mark.integration
def test_trigger_with_materialized_view_refresh(clean_db, refresh_trigger_tables):
    """Test auto-refresh triggers on materialized views"""

    class TestMatView(SamizdatMaterializedView):
        schema = "public"
        # Use the existing refresh_trigger_tables fixture
        refresh_triggers = {("public", "d")}
        sql_template = """
            ${preamble}
            SELECT COUNT(*) as total FROM d
            ${postamble}
        """

    # Get all samizdats including sidekicks (auto-generated triggers)
    from dbsamizdat.libgraph import depsort_with_sidekicks

    samizdats = depsort_with_sidekicks([TestMatView])

    # Should have generated sidekick trigger and function
    assert len(samizdats) > 1, "Should have generated sidekick triggers/functions"

    # Find the auto-generated trigger
    triggers = [s for s in samizdats if s.entity_type == entitypes.TRIGGER]
    assert len(triggers) > 0, "Should have auto-generated at least one trigger"

    # Check that trigger has autorefresher flag
    trigger = triggers[0]
    assert hasattr(trigger, "autorefresher")
    assert trigger.autorefresher is True


@pytest.mark.unit
def test_trigger_lsp_compliance_after_fix():
    """
    VERIFIES LSP FIX: Can now safely substitute trigger for samizdat.

    This test shows that after fixing the LSP violation, triggers can be
    used polymorphically with other Samizdat types.
    """
    from typing import Type

    from dbsamizdat.samizdat import Samizdat

    def process_samizdat(samizdat_cls: Type[Samizdat]) -> str:
        """
        Function that expects any Samizdat subclass.
        Should work with all Samizdat types per LSP.
        """
        # All Samizdats should have a proper schema (str or None)
        if samizdat_cls.schema is None:
            return "no_schema"
        else:
            return f"schema: {samizdat_cls.schema}"

    # Works with regular Samizdat
    from dbsamizdat.samizdat import SamizdatView

    class NormalView(SamizdatView):
        sql_template = "${preamble} SELECT 1 ${postamble}"

    result_view = process_samizdat(NormalView)
    assert result_view == "schema: public"

    # NOW ALSO WORKS with SamizdatTrigger (LSP compliant!)
    result_trigger = process_samizdat(UpdateTimestampTrigger)
    assert result_trigger == "schema: public"  # Same behavior as other Samizdats!

    # Both have consistent schema semantics
    assert NormalView.schema == UpdateTimestampTrigger.schema


@pytest.mark.unit
def test_trigger_identity_is_now_sensible():
    """
    VERIFIES LSP FIX: Trigger identity is now semantically correct.

    After the fix, triggers use proper schema and compose unique names
    that include the table reference without abusing the schema field.
    """
    # Normal samizdat
    normal_identity = TestTable.db_object_identity()
    assert normal_identity == '"public"."TestTable"'

    # Trigger's fq() now properly uses schema
    trigger_fq = UpdateTimestampTrigger.fq()
    # Schema is now correctly just "public", not the full table identity
    assert trigger_fq.schema == "public"
    # The table reference is in the object_name instead
    assert "TestTable" in trigger_fq.object_name


# ==================== Additional Verification Tests ====================


@pytest.mark.unit
def test_trigger_fq_uniqueness():
    """
    Verify that triggers on different tables have different fq() values.
    """

    class AnotherTable(SamizdatTable):
        sql_template = "${preamble} (id INTEGER) ${postamble}"

    class TriggerOnAnother(SamizdatTrigger):
        on_table = AnotherTable
        condition = "BEFORE UPDATE"
        sql_template = "${preamble} FOR EACH ROW EXECUTE PROCEDURE foo() ${postamble}"

    # Different tables should result in different fq() values
    fq1 = UpdateTimestampTrigger.fq()
    fq2 = TriggerOnAnother.fq()

    # Same schema (both public)
    assert fq1.schema == fq2.schema == "public"

    # But different object names (include table reference)
    assert fq1.object_name != fq2.object_name
    assert "TestTable" in fq1.object_name
    assert "AnotherTable" in fq2.object_name
