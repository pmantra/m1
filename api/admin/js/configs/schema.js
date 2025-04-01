import ObjectFieldTemplate from '../components/ObjectFieldTemplate.jsx';

export const schemaConfig = {
  schema: {
    type: 'object',
    properties: {
      questions: {
        type: 'array',
        title: '',
        items: {
          type: 'object',
          title: 'Question',
          properties: {
            body: {
              type: 'string',
              title: 'body',
              default: '',
            },
            widget: {
              type: 'object',
              title: '',
              properties: {
                type: {
                  title: 'widget',
                  type: 'string',
                  enum: [
                    'date',
                    'radio',
                    'textarea',
                    'freetextmulti',
                    'radio-color-callout',
                    'panel-multi-choice-sectioned',
                    'color-callout-checkboxes-sectioned',
                  ],
                },
              },
              dependencies: {
                type: {
                  oneOf: [
                    {
                      properties: {
                        type: {
                          enum: ['date'],
                        },
                      },
                    },
                    {
                      properties: {
                        type: {
                          enum: ['radio-color-callout'],
                        },
                        options: {
                          title: 'Options',
                          type: 'array',
                          items: {
                            title: 'Options',
                            type: 'object',
                            properties: {
                              label: {
                                type: 'string',
                                title: 'label',
                                default: '',
                              },
                              value: {
                                type: 'string',
                                title: 'value',
                                default: '',
                              },
                              next: {
                                type: 'number',
                                title: 'next',
                                default: '',
                              },
                            },
                          },
                        },
                      },
                    },
                    {
                      properties: {
                        type: {
                          enum: ['radio'],
                        },
                        options: {
                          title: 'Options',
                          type: 'array',
                          items: {
                            title: 'Options',
                            type: 'object',
                            properties: {
                              label: {
                                type: 'string',
                                title: 'label',
                                default: '',
                              },
                              value: {
                                type: 'string',
                                title: 'value',
                                default: '',
                              },
                              next: {
                                type: 'number',
                                title: 'next',
                                default: '',
                              },
                            },
                          },
                        },
                      },
                    },
                    {
                      properties: {
                        type: {
                          enum: ['freetextmulti'],
                        },
                        options: {
                          title: 'Options',
                          type: 'array',
                          items: {
                            title: 'Options',
                            type: 'object',
                            properties: {
                              label: {
                                type: 'string',
                                title: 'label',
                                default: '',
                              },
                              value: {
                                type: 'string',
                                title: 'value',
                                default: '',
                              },
                              placeholder: {
                                type: 'string',
                                title: 'placeholder',
                                default: '',
                              },
                              fieldtype: {
                                type: 'string',
                                title: 'fieldtype',
                                default: '',
                              },
                              required: {
                                type: 'boolean',
                                title: 'required',
                                default: false,
                              },
                            },
                          },
                        },
                      },
                    },
                    {
                      properties: {
                        type: {
                          enum: ['textarea'],
                        },
                        placeholder: {
                          type: 'string',
                        },
                      },
                    },
                    {
                      properties: {
                        type: {
                          enum: ['panel-multi-choice-sectioned'],
                        },
                        options: {
                          title: 'Options',
                          type: 'array',
                          items: {
                            title: 'Options',
                            type: 'object',
                            properties: {
                              id: {
                                type: 'number',
                                title: 'id',
                                default: '',
                              },
                              label: {
                                type: 'string',
                                title: 'label',
                                default: '',
                              },
                              value: {
                                type: 'string',
                                title: 'value',
                                default: '',
                              },
                            },
                          },
                        },
                        sections: {
                          type: 'array',
                          items: {
                            type: 'object',
                            properties: {
                              title: {
                                type: 'string',
                                title: 'title',
                                default: '',
                              },
                              items: {
                                type: 'array',
                                title: 'items',
                                items: {
                                  type: 'string',
                                  default: '',
                                },
                              },
                            },
                          },
                        },
                      },
                    },
                    {
                      properties: {
                        type: {
                          enum: ['color-callout-checkboxes-sectioned'],
                        },
                        options: {
                          title: 'Options',
                          type: 'array',
                          items: {
                            title: 'Options',
                            type: 'object',
                            properties: {
                              id: {
                                type: 'number',
                                title: 'id',
                                default: '',
                              },
                              label: {
                                type: 'string',
                                title: 'label',
                                default: '',
                              },
                              value: {
                                type: 'string',
                                title: 'value',
                                default: '',
                              },
                              other: {
                                type: 'boolean',
                                title: 'other',
                                default: '',
                              },
                            },
                          },
                        },
                        sections: {
                          type: 'array',
                          items: {
                            type: 'object',
                            properties: {
                              title: {
                                type: 'string',
                                title: 'title',
                                default: '',
                              },
                              items: {
                                type: 'array',
                                title: 'items',
                                items: {
                                  type: 'string',
                                  default: '',
                                },
                              },
                            },
                          },
                        },
                      },
                    },
                  ],
                },
              },
            },
            id: {
              type: 'integer',
              title: 'id',
              default: null,
            },
            next: {
              type: ['string'],
              title: 'next',
              default: '',
            },
            required: {
              type: 'boolean',
              title: 'Required',
              default: true,
            },
            export: {
              title: 'Export Topics',
              type: 'object',
              default: null,
              properties: Object.fromEntries(
                [
                  ['ANALYTICS', 'Export answers to the analytics data store.'],
                  ['FHIR', 'Export answers into structured FHIR data.'],
                ].map(([topic, description]) => [
                  topic,
                  {
                    type: 'object',
                    title: '',
                    description,
                    default: null,
                    properties: {
                      question_name: {
                        type: 'string',
                        title: 'Question Name',
                        default: null,
                      },
                      export_logic: {
                        type: 'string',
                        title: 'Export Logic',
                        enum: ['RAW', 'BMI', 'YES_NO', 'FILTER_NULLS', 'TEMPLATE_LABEL'],
                        enumNames: [
                          'Send the answer as is.',
                          'Determines body mass index risk flag from height and weight.',
                          "Interpret 'yes' as true and everything else as false.",
                          'Filter empty values from the list of answers provided.',
                          "Send the answer's UI template label.",
                        ],
                      },
                    },
                    dependencies: {
                      question_name: ['export_logic'],
                      export_logic: ['question_name'],
                    },
                  },
                ]),
              ),
            },
          },
        },
      },
    },
  },
  uiSchema: {
    questions: {
      items: {
        body: {
          'ui:widget': 'textarea',
        },
      },
    },
  },
  formData: {
    questions: [
      {
        body: '',
        id: null,
        widget: {
          type: '',
        },
        next: '',
        required: true,
      },
    ],
  },
  ObjectFieldTemplate,
};
