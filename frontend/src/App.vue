<template>
  <el-container style="min-height:100vh">
    <el-header style="background:#1a73e8;color:white;padding:0 24px;display:flex;align-items:center;justify-content:space-between">
      <h2 style="margin:0">🤖 Job Crawlers Dashboard</h2>
      <el-space>
        <el-tag v-for="p in platforms" :key="p" :type="activePlatform===p?'primary':'info'" style="cursor:pointer" @click="activePlatform=p">{{ p==='jobsdb'?'JobsDB':'CTGoodJobs' }}</el-tag>
      </el-space>
    </el-header>

    <el-main style="padding:16px">
      <!-- Stats Bar -->
      <el-row :gutter="12" style="margin-bottom:16px">
        <el-col :span="4" v-for="s in statItems" :key="s.key">
          <el-card shadow="hover" :body-style="{padding:'12px 16px'}">
            <div style="font-size:12px;color:#999">{{ s.label }}</div>
            <div style="font-size:24px;font-weight:700;color:#333">{{ s.value }}</div>
          </el-card>
        </el-col>
      </el-row>

      <!-- Config + Crawl -->
      <el-card style="margin-bottom:16px">
        <template #header><span>⚙️ 爬取配置</span></template>
        <el-row :gutter="12" align="middle">
          <el-col :span="14">
            <el-input v-model="config.keywords" placeholder="关键词，逗号分隔">
              <template #prepend>关键词</template>
            </el-input>
          </el-col>
          <el-col :span="5">
            <el-input-group>
              <template #prepend>月薪</template>
              <el-input-number v-model="config.salaryFrom" :min="0" :step="5000" controls-position="right" style="width:100px"/>
              <span style="padding:0 8px">-</span>
              <el-input-number v-model="config.salaryTo" :min="0" :step="5000" controls-position="right" style="width:100px"/>
            </el-input-group>
          </el-col>
          <el-col :span="5">
            <el-space>
              <el-button type="primary" @click="startCrawl" :loading="crawling" :disabled="crawling">
                {{ crawling ? '爬取中...' : '开始爬取' }}
              </el-button>
              <el-button v-if="crawling" @click="stopCrawl = true">停止</el-button>
            </el-space>
          </el-col>
        </el-row>
      </el-card>

      <!-- Crawl Log -->
      <el-card v-if="crawlLog.length > 0 || crawling" style="margin-bottom:16px">
        <template #header>
          <span>📋 爬取日志</span>
          <el-tag v-if="crawling" type="warning" size="small" style="margin-left:8px">进行中</el-tag>
        </template>
        <div ref="logBox" style="max-height:200px;overflow-y:auto;background:#1e1e1e;color:#d4d4d4;padding:12px;border-radius:4px;font-family:monospace;font-size:13px;white-space:pre-wrap">
          <div v-for="(line, i) in crawlLog" :key="i">{{ line }}</div>
          <div v-if="crawling" style="color:#888">⏳ 等待日志...</div>
        </div>
      </el-card>

      <!-- Job Table -->
      <el-card>
        <template #header>
          <span>📊 职位列表 ({{ totalJobs }})</span>
          <el-space style="margin-left:12px">
            <el-select v-model="filter.keyword" placeholder="关键词" clearable size="small" style="width:130px" @change="loadJobs">
              <el-option v-for="k in keywordsAvailable" :key="k" :label="k" :value="k"/>
            </el-select>
            <el-select v-model="filter.status" placeholder="状态" clearable size="small" style="width:130px" @change="loadJobs">
              <el-option label="未申请" value="pending"/>
              <el-option label="已申请" value="applied"/>
              <el-option label="外链" value="external"/>
              <el-option label="未知问题" value="unknown_questions"/>
              <el-option label="失败" value="failed"/>
            </el-select>
            <el-select v-model="filter.timeRange" placeholder="发布时间" clearable size="small" style="width:130px" @change="loadJobs">
              <el-option label="5天内" value="5d"/>
              <el-option label="5-10天" value="5-10d"/>
              <el-option label="10-20天" value="10-20d"/>
              <el-option label="20天以上" value="20d+"/>
            </el-select>
            <el-button type="success" size="small" @click="batchApply" :disabled="selectedIds.length===0">
              批量投递 ({{ selectedIds.length }})
            </el-button>
          </el-space>
        </template>

        <el-table :data="jobs" @selection-change="onSelect" v-loading="loading" stripe size="small" style="width:100%">
          <el-table-column type="selection" width="40"/>
          <el-table-column prop="id" label="#" width="50"/>
          <el-table-column prop="title" label="职位" min-width="250">
            <template #default="{row}">
              <a :href="row.job_link" target="_blank" style="color:#1a73e8;text-decoration:none;font-weight:500">
                {{ row.title }}
              </a>
              <div style="font-size:12px;color:#999;margin-top:2px">
                {{ row.company }} · {{ row.location }}
                <span v-if="row.salary"> · 💰 {{ row.salary }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="keyword" label="关键词" width="120"/>
          <el-table-column prop="posted_hours" label="发布" width="80" sortable>
            <template #default="{row}">
              {{ row.posted_hours ? (row.posted_hours<24 ? row.posted_hours+'h' : Math.floor(row.posted_hours/24)+'d') : '-' }}
            </template>
          </el-table-column>
          <el-table-column label="状态" width="120">
            <template #default="{row}">
              <el-tag v-if="row.applied" type="success" size="small">✅ 已申请</el-tag>
              <el-tag v-else-if="row.last_apply_status==='unknown_questions'" type="warning" size="small">⛔ 未知问题</el-tag>
              <el-tag v-else-if="!row.can_auto_apply" type="danger" size="small">🔗 外链</el-tag>
              <el-tag v-else-if="row.last_apply_status==='failed'" type="danger" size="small">❌ 失败</el-tag>
              <el-tag v-else type="info" size="small">待处理</el-tag>
            </template>
          </el-table-column>
        </el-table>

        <div style="margin-top:12px;display:flex;justify-content:center">
          <el-pagination
            v-model:current-page="pagination.page"
            :page-size="pagination.perPage"
            :total="totalJobs"
            layout="prev, pager, next, total"
            @current-change="loadJobs"
          />
        </div>
      </el-card>

      <!-- Apply Progress -->
      <el-card v-if="applying || applyResults.length > 0" style="margin-top:16px">
        <template #header>
          <span>📤 投递进度</span>
          <el-tag v-if="applying" type="warning" size="small" style="margin-left:8px">进行中</el-tag>
        </template>
        <div v-if="applying" style="color:#666;margin-bottom:8px">{{ applyCurrent }}</div>
        <el-table :data="applyResults" size="small">
          <el-table-column prop="id" label="#" width="50"/>
          <el-table-column prop="title" label="职位" min-width="200"/>
          <el-table-column label="结果" width="80">
            <template #default="{row}">
              <el-tag :type="row.success?'success':'danger'" size="small">{{ row.success ? '✅' : '❌' }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="output" label="详情" min-width="200">
            <template #default="{row}">{{ row.output }}</template>
          </el-table-column>
        </el-table>
      </el-card>
    </el-main>
  </el-container>
</template>

<script setup>
import { ref, reactive, onMounted, watch, nextTick, computed } from 'vue'
import { api, createSSE } from './api/index.js'

const platforms = ['jobsdb', 'ctgoodjobs']
const activePlatform = ref('jobsdb')
const loading = ref(false)
const crawling = ref(false)
const applying = ref(false)
const stopCrawl = ref(false)
const jobs = ref([])
const totalJobs = ref(0)
const selectedIds = ref([])
const keywordsAvailable = ref([])
const crawlLog = ref([])
const applyCurrent = ref('')
const applyResults = ref([])
const logBox = ref(null)

const config = reactive({ keywords: 'AI Agent,AI Developer,LLM Engineer,NLP,Generative AI', salaryFrom: 50000, salaryTo: 120000 })
const filter = reactive({ keyword: '', status: '', timeRange: '' })
const pagination = reactive({ page: 1, perPage: 20 })

const statItems = computed(() => {
  const s = stats.value || {}
  return [
    { key:'total', label:'总活跃', value:s.total||0 },
    { key:'today', label:'今日新', value:s.today_new||0 },
    { key:'applied', label:'已申请', value:s.applied||0 },
    { key:'external', label:'外链', value:s.external||0 },
    { key:'unknown', label:'待处理', value:s.unknown_questions||0 },
  ]
})

const stats = ref({})
async function loadStats() { stats.value = await api.stats(activePlatform.value) }

async function loadJobs() {
  loading.value = true
  try {
    const data = await api.jobs({
      platform: activePlatform.value, keyword: filter.keyword, status: filter.status,
      time_range: filter.timeRange,
      page: pagination.page, per_page: pagination.perPage, sort: 'posted_hours', order: 'asc'
    })
    jobs.value = data.jobs
    totalJobs.value = data.total
    keywordsAvailable.value = data.keywords_available || []
  } finally { loading.value = false }
}

function onSelect(rows) { selectedIds.value = rows.map(r => r.id) }

async function startCrawl() {
  crawlLog.value = []
  stopCrawl.value = false
  crawling.value = true
  try {
    await api.crawl({
      keywords: config.keywords,
      salary_from: config.salaryFrom, salary_to: config.salaryTo,
      platforms: [activePlatform.value], count: 100
    })
    // SSE 监听日志
    const sse = createSSE('/crawl/stream', { platform: activePlatform.value })
    sse.onMessage(data => {
      if (data.done) {
        crawling.value = false
        sse.close()
        loadStats()
        loadJobs()
      } else if (data.lines) {
        crawlLog.value.push(...data.lines)
        nextTick(() => { if (logBox.value) logBox.value.scrollTop = logBox.value.scrollHeight })
      }
    })
  } catch { crawling.value = false }
}

async function batchApply() {
  if (selectedIds.value.length === 0) return
  applyResults.value = []
  applying.value = true
  try {
    await api.apply({ platform: activePlatform.value, job_ids: selectedIds.value })
    const sse = createSSE('/apply/stream')
    sse.onMessage(data => {
      applyCurrent.value = data.current || ''
      if (Array.isArray(data.results)) applyResults.value = data.results
      if (data.done) { applying.value = false; sse.close(); loadStats(); loadJobs() }
    })
  } catch { applying.value = false }
}

watch(activePlatform, () => { loadStats(); loadJobs() })
onMounted(() => { loadStats(); loadJobs() })
</script>

<style>
body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f5f5 }
</style>
