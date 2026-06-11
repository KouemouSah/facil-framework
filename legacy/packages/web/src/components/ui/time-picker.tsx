'use client'

import { useMemo } from 'react'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Label } from '@/components/ui/label'

interface TimePickerProps {
  value: string // "HH:MM" format
  onChange: (value: string) => void
  label?: string
  minuteStep?: number // 1, 5, 15, 30 — default 15
  disabled?: boolean
}

export function TimePicker({
  value,
  onChange,
  label,
  minuteStep = 15,
  disabled = false,
}: TimePickerProps) {
  const [hour, minute] = useMemo(() => {
    const parts = value.split(':')
    return [parts[0] || '08', parts[1] || '00']
  }, [value])

  const hours = useMemo(
    () => Array.from({ length: 24 }, (_, i) => String(i).padStart(2, '0')),
    []
  )

  const minutes = useMemo(
    () =>
      Array.from({ length: Math.floor(60 / minuteStep) }, (_, i) =>
        String(i * minuteStep).padStart(2, '0')
      ),
    [minuteStep]
  )

  const handleHourChange = (h: string) => {
    onChange(`${h}:${minute}`)
  }

  const handleMinuteChange = (m: string) => {
    onChange(`${hour}:${m}`)
  }

  return (
    <div className="space-y-2">
      {label && <Label>{label}</Label>}
      <div className="flex items-center gap-1">
        <Select value={hour} onValueChange={handleHourChange} disabled={disabled}>
          <SelectTrigger className="w-[80px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {hours.map((h) => (
              <SelectItem key={h} value={h}>
                {h}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <span className="text-lg font-bold text-muted-foreground">:</span>
        <Select value={minute} onValueChange={handleMinuteChange} disabled={disabled}>
          <SelectTrigger className="w-[80px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {minutes.map((m) => (
              <SelectItem key={m} value={m}>
                {m}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
    </div>
  )
}
