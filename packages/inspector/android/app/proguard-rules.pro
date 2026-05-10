# ============================================================================
# Facil Inspector — ProGuard/R8 Rules
# ============================================================================

# React Native core
-keep class com.facebook.react.** { *; }
-keep class com.facebook.hermes.** { *; }
-keep class com.facebook.jni.** { *; }

# React Native Reanimated
-keep class com.swmansion.reanimated.** { *; }
-keep class com.facebook.react.turbomodule.** { *; }

# React Native Gesture Handler
-keep class com.swmansion.gesturehandler.** { *; }

# Expo modules
-keep class expo.modules.** { *; }
-keep class com.facebook.react.bridge.** { *; }

# Firebase (push notifications + storage)
-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }

# OkHttp (networking)
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }

# MMKV (encrypted storage)
-keep class com.tencent.mmkv.** { *; }

# Signature canvas (WebView)
-keep class com.nicegameslab.** { *; }

# Keep annotations
-keepattributes *Annotation*
-keepattributes SourceFile,LineNumberTable
-keepattributes Signature
-keepattributes Exceptions

# Don't warn about optional dependencies
-dontwarn com.facebook.react.**
-dontwarn expo.modules.**
