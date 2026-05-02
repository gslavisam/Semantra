from __future__ import annotations

from app.models.mapping import TransformationTemplate


TRANSFORMATION_TEMPLATES: list[TransformationTemplate] = [
    TransformationTemplate(
        template_id="trim_whitespace",
        name="Trim whitespace",
        description="Strip leading and trailing whitespace from the source column.",
        code_template='df_source["{source}"].astype(str).str.strip()',
    ),
    TransformationTemplate(
        template_id="lowercase_text",
        name="Lowercase text",
        description="Normalize the source column to lowercase text.",
        code_template='df_source["{source}"].astype(str).str.lower()',
    ),
    TransformationTemplate(
        template_id="uppercase_text",
        name="Uppercase text",
        description="Normalize the source column to uppercase text.",
        code_template='df_source["{source}"].astype(str).str.upper()',
    ),
    TransformationTemplate(
        template_id="title_case_text",
        name="Title-case text",
        description="Normalize the source column to title case.",
        code_template='df_source["{source}"].astype(str).str.title()',
    ),
    TransformationTemplate(
        template_id="email_local_part_title",
        name="Email local-part to title",
        description="Extract the email local-part, replace dots with spaces, and title-case the result.",
        code_template='df_source["{source}"].astype(str).str.split("@").str[0].str.replace(".", " ", regex=False).str.title()',
    ),
    TransformationTemplate(
        template_id="digits_only",
        name="Keep digits only",
        description="Remove every non-digit character from the source column.",
        code_template='df_source["{source}"].astype(str).str.replace(r"\\D+", "", regex=True)',
    ),
]


def list_transformation_templates() -> list[TransformationTemplate]:
    return list(TRANSFORMATION_TEMPLATES)