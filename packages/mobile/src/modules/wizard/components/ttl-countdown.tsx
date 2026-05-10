import { StyleSheet, View } from 'react-native';
import { Text } from 'react-native-paper';
import { MaterialCommunityIcons } from '@expo/vector-icons';

interface TTLCountdownProps {
  timeRemaining: number;
  isExpiring: boolean;
}

export function TTLCountdown({ timeRemaining, isExpiring }: TTLCountdownProps) {
  const minutes = Math.floor(timeRemaining / 60);
  const seconds = timeRemaining % 60;
  const color = isExpiring ? '#F44336' : '#757575';

  return (
    <View style={[styles.badge, { backgroundColor: isExpiring ? '#FFEBEE' : '#F5F5F5' }]}>
      <MaterialCommunityIcons name="clock-outline" size={14} color={color} />
      <Text style={[styles.text, { color }]}>
        {String(minutes).padStart(2, '0')}:{String(seconds).padStart(2, '0')}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8, paddingVertical: 3, borderRadius: 12, gap: 4 },
  text: { fontSize: 12, fontWeight: '600', fontVariant: ['tabular-nums'] },
});
