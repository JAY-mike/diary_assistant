import streamlit as st
import requests

#==================
#配置全局参数
API_URL = 'http://127.0.0.1:8002/diaries/'  #后端API地址
#==================

#设置页面标题和描述
st.set_page_config(page_title = '解压日记前端', page_icon = '📓',layout = 'centered')
st.title('解压日记前端')
st.markdown('在这里卸下防备，,记录真实的直接.')

#==================
# 模块一: 写日记(使用st.form表单提交，避免每次输入都触发请求)
#==================
st.header('写一篇新日记')

#使用form表单，保证只有点击提交按钮时才会触发请求
with st.form('diary_form', clear_on_submit = True):
    title = st.text_input('日记标题',placeholder = '例如:今天被clannad治愈了')
    content = st.text_area('日记内容',placeholder = '例如:今天看了clannad,感觉被治愈了,想记录一下这种感觉',height=150)
    mood = st.selectbox('选择心情',options=['开心','难过','平静','激动','其他'])

    #提交按钮
    submitted = st.form_submit_button('封存这一刻')

    if submitted:
        if not title or not content:
            st.warning("⚠️ 标题和正文不能为空哦！")
        else:
            #组装发给后端的数据（严格按照后端的DiaryCreate模型）
            payload = {
                "title": title,
                "content": content,
                "mood": mood
            }
            try:
                # 🚀 向 FastAPI 发起 POST 请求
                response = requests.post(API_URL, json=payload)
                if response.status_code ==200:
                    st.success("✨ 日记已成功保存入库！(数据已同步至 MySQL)")
                else:
                    st.error(f"❌ 保存失败，后端返回状态码: {response.status_code}")
            except requests.exceptions.ConnectionError:
                st.error("❌ 无法连接到后端API,请确保后端服务正在运行！")

st.divider() #分割线，视觉上区分写日记和看日记两个模块

#==================
# 🕰️ 模块二：时光倒流 (读取日记列表)
#==================
st.header('时光倒流：看看之前写了什么')

#点击按钮触发拉取
if st.button("🔄 刷新日记列表 (体验 Redis 极速缓存)"):
    try:
        # 🚀 向 FastAPI 发起 GET 请求 (限制先拉取最新的 10 条)
        response = requests.get(API_URL + "?skip=0&limit=10")

        if response.status_code == 200:
            diaries = response.json()

            if not diaries:
                st.info("📭 目前还没有日记哦，快去写一篇吧！")

            else:
                # 遍历日记，使用 expander (折叠面板) 优雅地展示
                for d in diaries:
                    #简单处理一下时间格式
                    created_time = d.get("created_at","").replace("T", " ")[:19]

                    #生成折叠面板的标题
                    expander_title = f"[{d.get('mood','未知心情')}] {d['title']} - {created_time}"

                    with st.expander(expander_title):
                        st.write(d['content'])
                        st.caption(f"系统 ID: {d['id']}")

                        # 为未来的 AI 功能预留位置
                        # if st.button(f"🤖 让 AI 分析这篇日记", key=f"ai_{d['id']}"):
                        #     st.toast("AI 接口待接入...")

        else:
            st.error(f"❌ 获取日记列表失败，后端返回状态码: {response.status_code}")
    except requests.exceptions.ConnectionError:
        st.error("❌ 无法连接到后端API,请确保后端服务正在运行！")           
