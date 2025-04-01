import enum
from typing import Optional


class Locale(str, enum.Enum):
    EN = "en"
    EN_US = "en-US"
    ES = "es"
    ES_419 = "es-419"
    FR = "fr"
    FR_CA = "fr-CA"
    FR_FR = "fr-FR"
    HI_IN = "hi-IN"
    IT_IT = "it-IT"
    JA_JP = "ja-JP"
    PL_PL = "pl-PL"
    PT_BR = "pt-BR"
    ZH_HANS = "zh-Hans"


def get_disclaimer_by_locale(locale: Optional[str]) -> Optional[str]:
    return DISCLAIMERS.get(locale, EN_DISCLAIMER)


EN_DISCLAIMER = (
    "Disclaimer: This content was prepared by Maven and is intended for informational purposes only. "
    "It should not be construed as legal, medical, or tax advice. It is not for use in the diagnosis "
    "of a condition, or in the cure, mitigation, treatment or prevention of a disease. For additional "
    "information and recommendations specific to you, please contact a licensed medical provider. "
    "Please note that this information may be subject to change based on additional guidance and "
    "legislative updates. ©2023 Maven Clinic Co. All Rights Reserved. "
)


ES_DISCLAIMER = (
    "Descargo de responsabilidad: El contenido fue preparado por Maven y está destinado únicamente "
    "a fines informativos. No debe interpretarse como asesoramiento legal, médico o impositivo. No "
    "debe usarse en el diagnóstico de una afección ni en la cura, mitigación, tratamiento o "
    "prevención de una enfermedad. Para obtener información adicional y recomendaciones específicas "
    "para usted, comuníquese con un proveedor médico autorizado. Tenga en cuenta que esta información "
    "puede estar sujeta a cambios en función de pautas adicionales y actualizaciones legislativas. "
    "©2023 Maven Clinic Co. Todos los derechos reservados."
)

FR_DISCLAIMER = (
    "Avis de non-responsabilité : ce contenu préparé par Maven n’est fourni qu’à titre informatif. Il "
    "ne doit pas être interprété comme un conseil médical, juridique, ou fiscal. Il n’est pas destiné "
    "au diagnostic d’un problème de santé, ni à la guérison, à l’atténuation, au traitement ou à la "
    "prévention d’une maladie. Pour obtenir plus d’informations et des recommandations spécifiques à "
    "votre cas, veuillez contacter un professionnel de santé agréé. Veuillez noter que ces "
    "informations peuvent faire l’objet de modifications en fonction de nouvelles directives et de "
    "mises à jour législatives. ©2023 Maven Clinic Co. Tous droits réservés."
)

HI_IN_DISCLAIMER = (
    "अस्वीकरण: यह सामग्री मेवन द्वारा तैयार की गई थी और केवल सूचनात्मक उद्देश्यों के लिए है। इसे "
    "कानूनी, चिकित्सा या कर सलाह के रूप में नहीं समझा जाना चाहिए। यह किसी स्थिति के निदान में, "
    "या इलाज, शमन, उपचार या किसी बीमारी की रोकथाम में उपयोग के लिए नहीं है। आपके लिए विशिष्ट अतिरिक्त "
    "जानकारी और अनुशंसाओं के लिए, कृपया एक लाइसेंस प्राप्त चिकित्सा प्रदाता से संपर्क करें। कृपया "
    "ध्यान दें कि यह जानकारी अतिरिक्त मार्गदर्शन और विधायी अपडेट के आधार पर परिवर्तन के अधीन हो सकती "
    "है। ©2023 Maven Clinic Co. सभी अधिकार सुरक्षित"
)


IT_IT_DISCLAIMER = (
    "Esclusione di responsabilità: Questo contenuto è stato preparato da Maven ed è destinato "
    "esclusivamente a scopi informativi. Non deve essere interpretato come una consulenza legale, "
    "medica o fiscale. Non è destinato all’uso nella diagnosi di una condizione o nella cura, "
    "mitigazione, trattamento o prevenzione di una malattia. Per ulteriori informazioni e "
    "raccomandazioni specifiche, contattare un operatore sanitario autorizzato. Si prega di notare "
    "che queste informazioni possono essere soggette a modifiche in base a ulteriori linee guida e "
    "aggiornamenti legislativi. ©2023 Maven Clinic Co. Tutti i diritti riservati."
)


JA_JP_DISCLAIMER = (
    "免責事項：本サイトの内容は、Maven Clinicによって作成されたものであり、情報提供のみを目的としています。法務、医療、"
    "または税務アドバイスとして解釈されるべきではありません。医療診断や疾病の治癒、緩和、治療または予防の代用として"
    "利用することを意図および想定するものではありません。ご自身のための追加情報や推奨事項については、医師その他の資格を"
    "持った医療提供者にご相談ください。なお、本サイトの情報は付加的なガイダンスおよび法律の改正に基づいて変更される"
    "可能性がありますのでご了承ください。©2023 Maven Clinic Co. All Rights Reserved."
)


PL_PL_DISCLAIMER = (
    "Wyłączenie odpowiedzialności: Treść ta została przygotowana przez firmę Maven i jest przeznaczona "
    "wyłącznie do celów informacyjnych. Nie należy jej interpretować jako porady medycznej, prawnej, "
    "ani podatkowej. Nie jest ona przeznaczona do stosowania w diagnozowaniu schorzeń ani w leczeniu, "
    "łagodzeniu, terapii lub zapobieganiu chorobom. W celu uzyskania dodatkowych informacji i zaleceń "
    "należy skontaktować się z lekarzem. Należy pamiętać, że informacje te mogą ulec zmianie w oparciu "
    "o dodatkowe wytyczne i aktualizacje ustawodawcze. ©2023 Maven Clinic Co. Wszelkie prawa zastrzeżone."
)

PT_BR_DISCLAIMER = "Isenção de responsabilidade: Este conteúdo foi preparado pela Maven e destina-se apenas a fins informativos. Não deve ser interpretado como aconselhamento jurídico, médico ou fiscal. Não se destina ao uso no diagnóstico de uma doença ou na cura, mitigação, tratamento ou prevenção de uma doença. Para obter informações adicionais e recomendações específicas a você, entre em contato com um médico licenciado. Observe que essas informações podem estar sujeitas a alterações com base em orientações adicionais e atualizações legislativas. © 2023 Maven Clinic Co. Todos os direitos reservados."

ZH_HANS_DISCLAIMER = "免责声明：此内容由 Maven 编制，仅供参考。不应将其解释为法律、医疗或税务建议。其不用于疾病诊断、治愈、缓解、治疗或预防疾病。如需了解特定于您的其他信息和建议，请联系有执照的医疗服务提供者。请注意，此信息可能会根据其他指南和立法更新而发生变化。©2023 Maven Clinic Co. 版权所有。"

DISCLAIMERS: dict[Optional[str], str] = {
    Locale.EN.value: EN_DISCLAIMER,
    Locale.EN_US.value: EN_DISCLAIMER,
    Locale.ES.value: ES_DISCLAIMER,
    Locale.ES_419.value: ES_DISCLAIMER,
    Locale.FR.value: FR_DISCLAIMER,
    Locale.FR_CA.value: FR_DISCLAIMER,
    Locale.FR_FR.value: FR_DISCLAIMER,
    Locale.HI_IN.value: HI_IN_DISCLAIMER,
    Locale.IT_IT.value: IT_IT_DISCLAIMER,
    Locale.JA_JP.value: JA_JP_DISCLAIMER,
    Locale.PL_PL.value: PL_PL_DISCLAIMER,
    Locale.PT_BR.value: PT_BR_DISCLAIMER,
    Locale.ZH_HANS.value: ZH_HANS_DISCLAIMER,
}
