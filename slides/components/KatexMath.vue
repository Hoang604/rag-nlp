<script setup lang="ts">
import { computed } from 'vue'
import katex from 'katex'
import 'katex/dist/katex.min.css'

interface Props {
  expr: string
  // Empty when rendering inline mathematical notation inside prose or diagram captions
  display?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  display: false,
})

const rendered = computed<string>(() =>
  katex.renderToString(props.expr, {
    displayMode: props.display,
    throwOnError: false,
  }),
)
</script>

<template>
  <span :class="props.display ? 'km-block' : 'km-inline'" v-html="rendered" />
</template>

<style scoped>
.km-block {
  display: block;
  margin: 0.2rem 0;
}

.km-inline {
  display: inline;
}
</style>
