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
