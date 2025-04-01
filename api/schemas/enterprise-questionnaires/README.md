## Enterprise Needs Assessment Schemas

These schemas uses [JSON Schema](http://json-schema.org/) specification to describe the needs assessment json document 
and it serves as the rule sets to validate them at the same time. More information about the JSON Schema is 
[here](https://spacetelescope.github.io/understanding-json-schema/index.html)

1.  Versioning
    Just like our API specs, these schemas are versioned to accommodate and manage change compatibility. 
    It's `#/properties/version` in the schema.

1.  File location
    Currently, schemas live in `api/schemas/enterprise-questionnaires`. They should also be available via `$SITE_URL/_app_support/*.json`,
    so we should probably copy them at build time from `api/schemas/enterprise-questionnaires` to `www/static/_app_support`.

1.  Structure
    * The schema document itself is a JSON document with a single object inside that defines data types and some simple validation rules.
    * `title` attribute throughout the schema document are decorative, serves as a comment and/or annotation for better matching/aligning items.
    * `id` and `$schema` are standard boilerplate attributes.
    * `defintions` is an object with predefined types that can be reused and referenced in the following schema.
    * The actual needs assessment document is an object with a `verson` string, `questions` and `answers` arrays.
    * Questions and answers should match 1:1 with JSON array's intrinsic ordering, `title` attribute is added for each item to assist. 
    Both questions and answers can be skipped safely without triggering a validation error. I chose to separate questions and answers 
    because it represents the minimal footprint when only questions or only answers are presented. But I am open to ideas to fold each answer under each question object.
    * Each question is a plain text question which is simply a string. Or it can be a combo question that has follow up questions, 
    in which case the question will be an object with a "parent" question attribute and follow up questions pertaining to the answers like "yes" or "no".
    Please see sample question and answers JSON documents for more details.
    * Each answer is defined by either one of the few answer types in `#/definitions` in the JSON schema document, a customized enumeration type
    or a conditional answer where the content of the answer (lower-cased) of the parent question will be the key to the object of the answer to the follow up question.

1.  Validation
    * There are many libraries and tools to validate the JSON schema, including for Python / JavaScript and Swift. 
    Partial list is at http://json-schema.org/implementations.html
    * Python implementation https://github.com/Julian/jsonschema
    * The Swift implementation is at https://github.com/kylef/JSONSchema.swift
    * `jsonschema`'s CLI command can be installed via `pip install jsonschema`. It can be a handy tool to debugging and build linting.

1.  Examples
    * Questions example: `schemas/enterprise-questionnaires/needs_assessment_pregnancy_questions.json`
    * Answers example: `schemas/enterprise-questionnaires/needs_assessment_pregnancy_sample_answers.json`
    * Schema: `schemas/enterprise-questionnaires/needs_assessment_pregnancy_schema.json`
