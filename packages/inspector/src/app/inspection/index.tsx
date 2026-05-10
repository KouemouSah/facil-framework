/**
 * Redirect /inspection → /inspections list (this route is not directly navigated to)
 */
import { Redirect } from 'expo-router';

export default function InspectionRedirect() {
  return <Redirect href="/(tabs)/inspections" />;
}
