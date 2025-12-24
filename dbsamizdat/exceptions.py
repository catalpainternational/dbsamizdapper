def sqlfmt(sql: str):
    return "\n".join("\t\t" + line for line in sql.splitlines())


class SamizdatException(Exception):
    def __init__(self, message, samizdat=None):
        self.message = message
        self.samizdat = samizdat

    def __str__(self):
        sd_subject = f"{repr(self.samizdat)} : " if self.samizdat else ""
        return f"{sd_subject}{self.message}"


class NameClashError(SamizdatException):
    pass


class UnsuitableNameError(SamizdatException):
    pass


class DanglingReferenceError(SamizdatException):
    pass


class TypeConfusionError(SamizdatException):
    pass


def _detect_error_pattern(error_msg: str, sql: str) -> str | None:
    """
    Detect common error patterns and provide helpful hints.

    Args:
        error_msg: The database error message
        sql: The SQL that was executed

    Returns:
        A helpful hint string, or None if no pattern matches
    """
    error_lower = error_msg.lower()
    sql_lower = sql.lower()

    # Signature duplication pattern: "syntax error at or near \"(\""
    if (
        'syntax error at or near "("' in error_lower
        and sql_lower.count("create function") > 0
        and sql_lower.count("()(") > 0
    ):
        return (
            "Signature duplication detected: function_arguments_signature was provided "
            "but the template also includes a function signature. "
            "Remove the signature from either the template or the function_arguments_signature attribute."
        )

    # Missing CREATE FUNCTION pattern
    if (
        'syntax error at or near "returns"' in error_lower
        and "create function" not in sql_lower
        and "returns" in sql_lower
    ):
        return (
            "Missing CREATE FUNCTION: The template includes RETURNS but no CREATE FUNCTION statement. "
            "Ensure your template starts with ${preamble} which includes CREATE FUNCTION."
        )

    # Invalid template variable pattern
    if 'syntax error at or near "$"' in error_lower or 'syntax error at or near "$"' in error_lower:
        return (
            "Invalid template variable: An unsubstituted template variable ($...) was found in the SQL. "
            "Check that all template variables (${preamble}, ${postamble}, ${samizdatname}) are properly used."
        )

    return None


class DatabaseError(SamizdatException):
    def __init__(
        self,
        message,
        dberror,
        samizdat,
        sql,
        template: str | None = None,
        substitutions: dict[str, str] | None = None,
    ):
        self.message = message
        self.dberror = dberror
        self.samizdat = samizdat
        self.sql = sql
        self.template = template
        self.substitutions = substitutions

    def __str__(self):
        error_msg = str(self.dberror)
        hint = _detect_error_pattern(error_msg, self.sql)

        # Build context information
        context_parts = []

        # Show template if available
        if self.template:
            context_parts.append(f"Original template:\n{sqlfmt(self.template)}")

        # Show substitutions if available
        if self.substitutions:
            sub_lines = "\n".join(f"  ${key} = {value!r}" for key, value in sorted(self.substitutions.items()))
            context_parts.append(f"Template variable substitutions:\n{sub_lines}")

        # Show function signature if applicable
        if self.samizdat and hasattr(self.samizdat, "function_arguments_signature"):
            func_sig = getattr(self.samizdat, "function_arguments_signature", "")
            if func_sig:
                context_parts.append(f"function_arguments_signature: {func_sig!r}")
            else:
                context_parts.append("function_arguments_signature: '' (empty)")

        context = "\n\n".join(context_parts) if context_parts else None

        # Build error message
        result = f"""
            While executing:
            {sqlfmt(self.sql)}

            a DB error was raised:
            {error_msg}
        """

        if context:
            result += f"\n\nTemplate processing context:\n{context}"

        if hint:
            result += f"\n\n💡 Hint: {hint}"

        result += f"""

            while we were processing the samizdat:
            {repr(self.samizdat)}

            furthermore:
            {self.message}
        """

        return result


class DependencyCycleError(SamizdatException):
    def __init__(self, message, samizdats):
        self.message = message
        self.samizdats = samizdats

    def __str__(self):
        sd_subjects = ", ".join(self.samizdats)
        return f"{sd_subjects} : {self.message}"


class FunctionSignatureError(SamizdatException):
    def __init__(self, samizdat, candidate_arguments: list[str]):
        self.samizdat = samizdat
        self.candidate_arguments = candidate_arguments

    def __str__(self):
        try:
            sd_subject = repr(self.samizdat)
        except Exception:
            sd_subject = f"<samizdat {type(self.samizdat).__name__}>"
        
        try:
            create_sql = sqlfmt(self.samizdat.create())
        except Exception as e:
            create_sql = f"<error generating create SQL: {e}>"
        
        try:
            db_identity = self.samizdat.db_object_identity
        except Exception as e:
            db_identity = f"<error: {e}>"
        
        try:
            func_args = getattr(self.samizdat, 'function_arguments', None)
            if func_args is None:
                func_args = getattr(self.samizdat, 'function_arguments_signature', '')
            func_args_str = f"({func_args})"
        except Exception as e:
            func_args_str = f"<error: {e}>"
        
        candidate_args = "\n".join(self.candidate_arguments) if self.candidate_arguments else "<none>"
        args_herald = (
            f"the following candidates:\n{candidate_args}"
            if len(self.candidate_arguments) > 1
            else f'"{candidate_args}"'
        )
        return f"""
            After executing:
            {create_sql}

            which we did in order to create the samizdat function:
            {sd_subject}

            we were not able to identify the resulting database function via its call signature of:
            {db_identity}

            because, we figure, that is not actually the effective call signature resulting from the function arguments, which are:
            "{func_args_str}"

            We queried the database to find out what the effective call argument signature should be instead, and came up with:
            {args_herald}

            HINT: Amend the {sd_subject} .function_arguments_signature and/or .function_arguments attributes.
            For more information, consult the README."""
