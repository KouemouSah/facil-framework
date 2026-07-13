{{- define "facil.fullname" -}}
{{- printf "facil-%s" .name -}}
{{- end -}}

{{- define "facil.labels" -}}
app.kubernetes.io/name: facil
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "facil.selectorLabels" -}}
app.kubernetes.io/name: facil
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
