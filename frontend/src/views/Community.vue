<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { message, Modal } from 'ant-design-vue'
import {
  PlusOutlined,
  LikeOutlined,
  LikeFilled,
  MessageOutlined,
  EyeOutlined,
  DeleteOutlined
} from '@ant-design/icons-vue'
import {
  getPosts,
  createPost,
  getPost,
  likePost,
  getComments,
  createComment,
  deleteComment
} from '@/api/community'

const PAGE_SIZE = 9

// 筛选标签：公司名走后端的 company_name，关键词走后端的 keyword。
// 两种不同维度的筛选项分开传参，不再在前端做"只筛当前页"的假过滤。
const TABS = [
  { label: '全部' },
  { label: '字节', company: '字节' },
  { label: '阿里', company: '阿里' },
  { label: '腾讯', company: '腾讯' },
  { label: '美团', company: '美团' },
  { label: '算法', keyword: '算法' },
  { label: '后端', keyword: '后端' },
  { label: '前端', keyword: '前端' }
]
const activeIdx = ref(0)

const posts = ref<any[]>([])
const loading = ref(true)
const loadingMore = ref(false)
const page = ref(1)
const hasMore = ref(false)
const loadError = ref('')

const likingIds = ref<Set<number>>(new Set())

// 详情弹窗
const showDetail = ref(false)
const detail = ref<any>(null)
const detailLoading = ref(false)
const comments = ref<any[]>([])
const commentText = ref('')
const postingComment = ref(false)

// 发布
const showCreate = ref(false)
const submitting = ref(false)
const form = ref({ title: '', content: '', company_name: '', position_name: '' })

// ---- 时间：显示成「3 天前」而不是原始时间戳 ----
function timeAgo(iso: string | null): string {
  if (!iso) return ''
  const t = new Date(iso).getTime()
  if (isNaN(t)) return iso.slice(0, 10)
  const min = Math.floor((Date.now() - t) / 60000)
  if (min < 1) return '刚刚'
  if (min < 60) return `${min} 分钟前`
  const hours = Math.floor(min / 60)
  if (hours < 24) return `${hours} 小时前`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days} 天前`
  return iso.slice(0, 10)
}

// ---- 列表 ----
async function load(reset = false) {
  if (reset) {
    page.value = 1
    loading.value = true
  } else {
    loadingMore.value = true
  }
  try {
    const tab = TABS[activeIdx.value] as any
    const list: any[] = (await getPosts({
      page: page.value,
      page_size: PAGE_SIZE,
      company_name: tab.company,
      keyword: tab.keyword
    })) || []
    posts.value = reset ? list : [...posts.value, ...list]
    hasMore.value = list.length === PAGE_SIZE
    loadError.value = ''
  } catch (e: any) {
    // 失败就如实显示，不要塞假帖子冒充成功
    if (reset) posts.value = []
    loadError.value = e?.message || '加载失败'
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

function switchTab(i: number) {
  if (activeIdx.value === i) return
  activeIdx.value = i
  load(true)
}

function loadMore() {
  if (loadingMore.value || !hasMore.value) return
  page.value += 1
  load(false)
}

// ---- 点赞（乐观更新，失败回滚）----
async function handleLike(p: any) {
  if (likingIds.value.has(p.id)) return
  likingIds.value.add(p.id)

  const prevLiked = p.is_liked
  const prevCount = p.like_count || 0
  p.is_liked = !prevLiked
  p.like_count = prevCount + (p.is_liked ? 1 : -1)
  syncDetail(p)

  try {
    const res: any = await likePost(p.id)
    if (res?.like_count != null) p.like_count = res.like_count
    p.is_liked = !!res?.is_liked
    syncDetail(p)
  } catch {
    p.is_liked = prevLiked
    p.like_count = prevCount
    syncDetail(p)
    message.error('点赞失败，请稍后再试')
  } finally {
    setTimeout(() => likingIds.value.delete(p.id), 300)
  }
}

/** 详情弹窗和列表是同一篇帖子时，把点赞状态同步过去 */
function syncDetail(p: any) {
  if (detail.value && detail.value.id === p.id) {
    detail.value.like_count = p.like_count
    detail.value.is_liked = p.is_liked
  }
}

// ---- 详情弹窗 ----
async function openDetail(p: any) {
  showDetail.value = true
  detail.value = null
  comments.value = []
  commentText.value = ''
  detailLoading.value = true
  try {
    const [d, cs]: any[] = await Promise.all([getPost(p.id), getComments(p.id)])
    detail.value = d
    comments.value = Array.isArray(cs) ? cs : []
    p.view_count = d?.view_count
    p.comments = comments.value.length
  } catch {
    message.error('这篇面经打开失败，请稍后再试')
    showDetail.value = false
  } finally {
    detailLoading.value = false
  }
}

// ---- 评论 ----
async function submitComment() {
  const text = commentText.value.trim()
  if (!text) {
    message.warning('先写点什么再发')
    return
  }
  if (!detail.value) return
  postingComment.value = true
  try {
    const c: any = await createComment(detail.value.id, text)
    comments.value = [c, ...comments.value] // 最新在最上面
    commentText.value = ''
    const p = posts.value.find((x) => x.id === detail.value!.id)
    if (p) p.comments = comments.value.length
  } catch {
    /* 错误提示由请求拦截器统一处理 */
  } finally {
    postingComment.value = false
  }
}

function removeComment(c: any) {
  Modal.confirm({
    title: '删除这条评论？',
    okText: '删除',
    okType: 'danger',
    cancelText: '取消',
    onOk: async () => {
      await deleteComment(c.id)
      comments.value = comments.value.filter((x) => x.id !== c.id)
      const p = posts.value.find((x) => x.id === detail.value?.id)
      if (p) p.comments = comments.value.length
      message.success('已删除')
    }
  })
}

// ---- 发布 ----
async function handleCreate() {
  if (!form.value.title.trim()) {
    message.warning('请填写标题')
    return
  }
  if (!form.value.content.trim()) {
    message.warning('请填写正文')
    return
  }
  submitting.value = true
  try {
    await createPost(form.value)
    message.success('已发布')
    showCreate.value = false
    form.value = { title: '', content: '', company_name: '', position_name: '' }
    await load(true)
  } catch {
    // 失败时保持弹窗打开、内容不丢；错误提示由拦截器统一弹
  } finally {
    submitting.value = false
  }
}

onMounted(() => load(true))
</script>

<template>
  <div class="page-container community-page">
    <header class="page-head">
      <h2>📖 面经社区</h2>
      <p class="sub">看看别人怎么面的，也把你的经历写下来</p>
    </header>

    <!-- 筛选 -->
    <div class="tabs-bar glass-card">
      <span
        v-for="(t, i) in TABS"
        :key="t.label"
        :class="['tab-item', { active: activeIdx === i }]"
        @click="switchTab(i)"
      >{{ t.label }}</span>
    </div>

    <!-- 列表 -->
    <div v-if="loading" class="empty-block">加载中…</div>

    <div v-else-if="loadError" class="empty-block">
      面经没加载出来（{{ loadError }}）。检查一下网络，或者稍后刷新重试
    </div>

    <div v-else-if="posts.length" class="post-grid">
      <article
        v-for="p in posts"
        :key="p.id"
        class="post-card glass-card"
        @click="openDetail(p)"
      >
        <div class="post-head">
          <div class="author">
            <div class="avatar">
              <img v-if="p.avatar" :src="p.avatar" :alt="p.author" />
              <span v-else>{{ (p.author || '匿').slice(0, 1) }}</span>
            </div>
            <div>
              <div class="author-name">{{ p.author || '匿名' }}</div>
              <div class="post-date">{{ timeAgo(p.created_at) }}</div>
            </div>
          </div>
          <div class="tags">
            <span v-if="p.company_name" class="chip chip-coral">{{ p.company_name }}</span>
            <span v-if="p.position_name" class="chip chip-turquoise">{{ p.position_name }}</span>
          </div>
        </div>

        <h3 class="post-title">{{ p.title }}</h3>
        <p class="post-excerpt">{{ p.content?.slice(0, 100) }}{{ (p.content?.length || 0) > 100 ? '…' : '' }}</p>

        <div class="post-foot">
          <span
            :class="['foot-item', 'like-btn', { liked: p.is_liked }]"
            @click.stop="handleLike(p)"
          >
            <LikeFilled v-if="p.is_liked" />
            <LikeOutlined v-else />
            {{ p.like_count || 0 }}
          </span>
          <span class="foot-item"><MessageOutlined /> {{ p.comments || 0 }}</span>
          <span class="foot-item read-more">读全文</span>
        </div>
      </article>
    </div>

    <div v-else class="empty-block">
      这个分类下还没有面经。换个标签看看，或者点右下角写下你的第一场
    </div>

    <div v-if="!loading && posts.length" class="more-bar">
      <a v-if="hasMore" @click="loadMore">{{ loadingMore ? '加载中…' : '加载更多' }}</a>
      <span v-else class="no-more">没有更多了</span>
    </div>

    <!-- 发布 -->
    <button class="fab" title="发布面经" @click="showCreate = true">
      <PlusOutlined />
    </button>

    <a-modal v-model:open="showCreate" title="✍️ 写面经" :footer="null" :width="520">
      <div class="create-form">
        <a-input
          v-model:value="form.title"
          placeholder="标题，如：阿里后端一面复盘"
          size="large"
          :maxlength="128"
          show-count
        />
        <div class="two-col">
          <a-input v-model:value="form.company_name" placeholder="公司（可选）" :maxlength="128" />
          <a-input v-model:value="form.position_name" placeholder="岗位（可选）" :maxlength="128" />
        </div>
        <a-textarea
          v-model:value="form.content"
          :rows="8"
          placeholder="面试问了什么、你怎么答的、哪里踩了坑……"
          :maxlength="20000"
          show-count
        />
        <div class="actions">
          <a-button class="btn-outline" @click="showCreate = false">取消</a-button>
          <a-button class="btn-coral" :loading="submitting" @click="handleCreate">发布</a-button>
        </div>
      </div>
    </a-modal>

    <!-- 详情 + 评论区 -->
    <a-modal
      v-model:open="showDetail"
      :footer="null"
      :width="680"
      :title="detail?.title || '面经详情'"
    >
      <div v-if="detailLoading" class="empty-block">加载中…</div>

      <div v-else-if="detail" class="detail-wrap">
        <div class="detail-head">
          <div class="avatar">
            <img v-if="detail.avatar" :src="detail.avatar" :alt="detail.author" />
            <span v-else>{{ (detail.author || '匿').slice(0, 1) }}</span>
          </div>
          <div class="detail-meta">
            <div class="author-name">{{ detail.author || '匿名' }}</div>
            <div class="post-date">{{ timeAgo(detail.created_at) }}</div>
          </div>
          <div class="tags">
            <span v-if="detail.company_name" class="chip chip-coral">{{ detail.company_name }}</span>
            <span v-if="detail.position_name" class="chip chip-turquoise">{{ detail.position_name }}</span>
          </div>
        </div>

        <p class="detail-body">{{ detail.content }}</p>

        <div class="detail-foot">
          <span
            :class="['foot-item', 'like-btn', { liked: detail.is_liked }]"
            @click="handleLike(detail)"
          >
            <LikeFilled v-if="detail.is_liked" />
            <LikeOutlined v-else />
            {{ detail.like_count || 0 }}
          </span>
          <span class="foot-item"><MessageOutlined /> {{ comments.length }}</span>
          <span class="foot-item"><EyeOutlined /> {{ detail.view_count || 0 }}</span>
        </div>

        <div class="comment-sec">
          <div class="comment-input">
            <a-textarea
              v-model:value="commentText"
              :rows="2"
              :maxlength="1000"
              placeholder="说点什么…（最多 1000 字）"
            />
            <a-button class="btn-coral" :loading="postingComment" @click="submitComment">
              发表评论
            </a-button>
          </div>

          <div v-if="comments.length" class="comment-list">
            <div v-for="c in comments" :key="c.id" class="comment-item">
              <div class="avatar small">
                <img v-if="c.avatar" :src="c.avatar" :alt="c.author" />
                <span v-else>{{ (c.author || '匿').slice(0, 1) }}</span>
              </div>
              <div class="comment-main">
                <div class="comment-top">
                  <span class="author-name">{{ c.author || '匿名' }}</span>
                  <span class="post-date">{{ timeAgo(c.created_at) }}</span>
                  <a
                    v-if="c.is_mine || detail.is_author"
                    class="comment-del"
                    @click="removeComment(c)"
                  >
                    <DeleteOutlined /> 删除
                  </a>
                </div>
                <div class="comment-text">{{ c.content }}</div>
              </div>
            </div>
          </div>
          <p v-else class="empty-block">还没有评论，来做第一个说话的人</p>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<style scoped>
.tabs-bar {
  display: flex;
  gap: 8px;
  padding: 12px 16px;
  margin-bottom: 20px;
  overflow-x: auto;
}
.tab-item {
  padding: 6px 18px;
  border-radius: 20px;
  font-size: 13px;
  color: #82789a;
  background: rgba(140, 110, 170, 0.06);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s;
}
.tab-item:hover { color: #3d3848; }
.tab-item.active {
  background: linear-gradient(135deg, #ff8e7b 0%, #ffb4a0 100%);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(255, 142, 123, 0.3);
}

.post-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}
.post-card {
  padding: 20px;
  cursor: pointer;
  transition: transform 0.15s, box-shadow 0.15s;
}
.post-card:hover { transform: translateY(-3px); box-shadow: 0 10px 26px rgba(140, 110, 170, 0.12); }

.post-head { display: flex; justify-content: space-between; gap: 10px; margin-bottom: 12px; }
.author { display: flex; gap: 10px; align-items: center; min-width: 0; }

.avatar {
  width: 36px;
  height: 36px;
  flex: none;
  border-radius: 50%;
  overflow: hidden;
  background: linear-gradient(135deg, #b49ee8, #ffb4a0);
  color: #fff;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}
.avatar img { width: 100%; height: 100%; object-fit: cover; }
.avatar.small { width: 30px; height: 30px; font-size: 13px; }

.author-name { font-size: 13px; font-weight: 600; color: #3d3848; }
.post-date { font-size: 11px; color: #82789a; }
.tags { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end; }
.chip { font-size: 11px; padding: 2px 10px; border-radius: 10px; white-space: nowrap; }
.chip-coral { background: rgba(255, 142, 123, 0.15); color: #ff8e7b; }
.chip-turquoise { background: rgba(60, 205, 182, 0.15); color: #3ccdb6; }

.post-title { font-size: 15px; font-weight: 700; color: #3d3848; line-height: 1.5; margin: 0 0 6px; }
.post-excerpt { font-size: 13px; color: #82789a; line-height: 1.6; margin: 0; }
.post-foot { margin-top: 14px; display: flex; gap: 16px; font-size: 12px; color: #82789a; }
.foot-item { display: inline-flex; align-items: center; gap: 4px; }
.read-more { margin-left: auto; color: #ff8e7b; }

.like-btn { cursor: pointer; transition: color 0.15s, transform 0.15s; }
.like-btn:hover { color: #ff8e7b; transform: scale(1.08); }
.like-btn.liked { color: #ff4d4f; font-weight: 700; }
.like-btn.liked:hover { color: #ff7875; }

.more-bar { margin-top: 20px; text-align: center; }
.more-bar a { color: #ff8e7b; cursor: pointer; font-size: 13px; }
.more-bar a:hover { text-decoration: underline; }
.no-more { font-size: 12px; color: #a79fbb; }

.fab {
  position: fixed;
  right: 32px;
  bottom: 32px;
  width: 60px;
  height: 60px;
  border-radius: 50%;
  border: none;
  background: linear-gradient(135deg, #ff8e7b 0%, #ffb4a0 50%, #f2a0b6 100%);
  color: #fff;
  font-size: 26px;
  box-shadow: 0 10px 24px rgba(255, 142, 123, 0.4);
  cursor: pointer;
  z-index: 10;
  transition: transform 0.15s;
}
.fab:hover { transform: scale(1.05); }

.create-form { display: flex; flex-direction: column; gap: 12px; }
.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 8px; }

/* ---- 详情弹窗 ---- */
.detail-wrap { max-height: 64vh; overflow-y: auto; padding-right: 4px; }
.detail-head { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.detail-meta { flex: 1; min-width: 0; }
.detail-body {
  margin: 0 0 16px;
  font-size: 14px;
  line-height: 1.85;
  color: #3d3848;
  white-space: pre-line;
}
.detail-foot {
  display: flex;
  gap: 18px;
  font-size: 12px;
  color: #82789a;
  padding-bottom: 16px;
  border-bottom: 1px solid rgba(140, 110, 170, 0.12);
}

.comment-sec { margin-top: 18px; }
.comment-input { display: flex; gap: 10px; align-items: flex-end; margin-bottom: 16px; }
.comment-input :deep(textarea) { resize: none; }

.comment-list { display: flex; flex-direction: column; gap: 14px; }
.comment-item { display: flex; gap: 10px; }
.comment-main { flex: 1; min-width: 0; }
.comment-top { display: flex; align-items: center; gap: 8px; }
.comment-del {
  margin-left: auto;
  font-size: 12px;
  color: #a79fbb;
  cursor: pointer;
}
.comment-del:hover { color: #d9363e; }
.comment-text {
  margin-top: 4px;
  font-size: 13px;
  color: #3d3848;
  line-height: 1.7;
  white-space: pre-line;
}

@media (max-width: 760px) {
  .two-col { grid-template-columns: 1fr; }
}
</style>
