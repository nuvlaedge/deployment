{{/*
Expand the name of the chart.
*/}}
{{- define "nuvlaedge.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Define the namespace based on the NUVLAEDGE_UUID
*/}}
{{- define "nuvlaedge.namespace" -}}
{{- if .Values.NUVLAEDGE_UUID }}
{{- .Values.NUVLAEDGE_UUID | replace "/" "-" }}
{{- else }}
nuvlaedge
{{- end }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "nuvlaedge.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "nuvlaedge.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "nuvlaedge.labels" -}}
helm.sh/chart: {{ include "nuvlaedge.chart" . }}
nuvlaedge.component: "True"
nuvlaedge.deployment: "production"
{{ include "nuvlaedge.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Common peripheral manager labels
*/}}
{{- define "nuvlaedge.peripheral-manager.labels" -}}
nuvlaedge.peripheral.component: "True"
{{- end }}

{{/*
Selector labels
*/}}
{{- define "nuvlaedge.selectorLabels" -}}
app.kubernetes.io/name: {{ include "nuvlaedge.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Create the name of the service account to use
*/}}
{{- define "nuvlaedge.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "nuvlaedge.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}
