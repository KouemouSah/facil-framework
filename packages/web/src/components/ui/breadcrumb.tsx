'use client'

import { ChevronRight, Home } from "lucide-react"
import Link from "next/link"
import { Fragment } from "react"
import { useLocale } from "next-intl"

export interface BreadcrumbItem {
  label: string
  href?: string
}

export interface BreadcrumbProps {
  items: BreadcrumbItem[]
  className?: string
}

export function Breadcrumb({ items, className = "" }: BreadcrumbProps) {
  const locale = useLocale()

  return (
    <nav aria-label="Breadcrumb" className={`flex items-center space-x-2 text-sm ${className}`}>
      {/* Home - use current locale */}
      <Link
        href={`/${locale}`}
        className="text-muted-foreground hover:text-foreground transition-colors flex items-center"
      >
        <Home className="h-4 w-4" />
        <span className="sr-only">Home</span>
      </Link>

      {/* Breadcrumb items */}
      {items.map((item, index) => {
        const isLast = index === items.length - 1

        return (
          <Fragment key={index}>
            <ChevronRight className="h-4 w-4 text-muted-foreground" />
            {item.href && !isLast ? (
              <Link
                href={item.href}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                {item.label}
              </Link>
            ) : (
              <span className={isLast ? "text-foreground font-medium" : "text-muted-foreground"}>
                {item.label}
              </span>
            )}
          </Fragment>
        )
      })}
    </nav>
  )
}

export default Breadcrumb
