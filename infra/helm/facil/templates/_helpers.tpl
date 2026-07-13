{{- define "facil.fullname" -}}
{{- printf "facil-%s" .name -}}
{{- end -}}

{{- define "facil.labels" -}}
app.kubernetes.io/name: facil
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
SEC-018 : app.kubernetes.io/instance DOIT faire partie du selector. Sans lui,
deux releases (ex. "facil" et "facil-staging") dans le MEME namespace ont des
Service/Deployment dont les selecteurs ne different que par facil.component --
identiques entre releases -- donc les Service de l'une selectionnent aussi les
pods de l'autre (et vice-versa). Attention : ce helper est aussi utilise par
NetworkPolicy (networkpolicy.yaml), qui cible cependant directement le label
`facil.component` (matchLabels/matchExpressions), jamais ce define dans son
integralite -- ajouter une cle ICI ne desactive donc pas son ciblage (verifie :
infra/helm/facil/tests/guard_networkpolicy.py + test_guard_networkpolicy.py).
*/}}
{{- define "facil.selectorLabels" -}}
app.kubernetes.io/name: facil
app.kubernetes.io/instance: {{ .Release.Name }}
facil.component: {{ .component }}
{{- end -}}

{{/*
imagePullSecrets — utilisé par les 3 workloads qui pullent ghcr.io/<owner>/facil-*
(backend, frontend, db-init). Ne rend RIEN si la liste est vide (pull anonyme).
Appel : {{- include "facil.imagePullSecrets" . | nindent 6 }} dans un podSpec.
*/}}
{{- define "facil.imagePullSecrets" -}}
{{- with .Values.global.imagePullSecrets }}
imagePullSecrets:
{{- toYaml . | nindent 2 }}
{{- end }}
{{- end -}}
