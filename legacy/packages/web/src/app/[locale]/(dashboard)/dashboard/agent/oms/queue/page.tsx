'use client'

/**
 * OMS Queue — Active obligations for processing
 *
 * Renders the canonical OMS queue page (same as /dashboard/agent/oms).
 * This route exists so the sidebar menu item "Obligations > En Curso"
 * resolves to a real page instead of 404.
 *
 * @route /[locale]/dashboard/agent/oms/queue
 */

import OMSAgentDashboardPage from '../page'

export default OMSAgentDashboardPage
