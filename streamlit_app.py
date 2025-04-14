import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt

plt.rcParams["font.family"] = "Hiragino Maru Gothic Pro"
from groq import Groq
from dotenv import load_dotenv
import os
import io

# .envファイルからAPIキーを読み込む
load_dotenv(dotenv_path="gpt-key.env")

# Groqクライアントの初期化
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# UIスタイル設定
# 背景白＋文字黒
st.markdown(
    """
<style>
    html, body, [class*="css"] {
        background-color: #ffffff;
        color: #000000;
        font-family: 'Noto Sans JP', sans-serif;
    }
    .stApp {
        background: linear-gradient(to bottom, #b0c4d8, #9eb3c7);
        color: #000000;
        font-family: 'Noto Sans JP', sans-serif;
    }
    h1, h2, h3 {
        color: #222222;
    }

    p, span, label, div {
        color: #ffffff;
    }    
    @media (max-width: 600px) {
        h1 {
            font-size: 1.6rem !important;
            text-align: center;
        }
        p, label, input, button {
            font-size: 0.95rem !important;
        }
        .stApp {
            padding: 10px;
        }
    }    
</style>
""",
    unsafe_allow_html=True,
)

# タイトル
# st.title("📘 BOM差分チェッカー")
st.markdown(
    """
<div style='background: linear-gradient(to bottom, #7a8ea2, #5a6e82); padding: 20px; border-radius: 20px;'>
    <h1 style='font-size: 38px; color: #333333;'>📊 在庫差分チェックツール</h1>
    <p style='color: #444;'>理論消費量と実消費量の差異をグラフとAIで分析</p>
</div>
""",
    unsafe_allow_html=True,
)

# ファイルアップロードUI
uploaded_file = st.file_uploader(
    "🔽 比較用のExcelファイルをアップロードしてください", type=["xlsx", "csv"]
)

# ファイルがああぷロードされた場合の処理
if uploaded_file is not None:
    # ファイル読み込み
    try:
        if uploaded_file.name.endswith(".xlsx"):
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)

        # バリデーションチェック
        validation_errors = []

        # ①数値チェック
        for col in ["理論消費量", "実消費量"]:
            if not pd.api.types.is_numeric_dtype(df[col]):
                validation_errors.append(
                    f"❌ {col} に数値以外のデータが含まれています。"
                )

        # ②不正文字チェック
        for col in ["品目コード", "品目名"]:
            if df[col].str.contains(r"[^\w\s\-ー・ぁ-んァ-ン一-龥]", regex=True).any():
                validation_errors.append(
                    f"❌ {col} に不正な記号や文字が含まれています。"
                )

        # ③ブランクチェック（全列）
        if df.isnull().values.any():
            validation_errors.append("❌ データに空欄（NaN）が含まれています。")

        # エラー表示
        if validation_errors:
            for msg in validation_errors:
                st.error(msg)
            st.stop()  # バリデーションに引っかかったら処理を止める

        st.success("✅ アップロード成功！")
        st.subheader("🧾 アップロードされたデータ")
        st.dataframe(df)

        # 差分チェック処理
        df["差分"] = df["実消費量"] - df["理論消費量"]

        # 差分が0ではないレコードを抽出
        diff_df = df[df["差分"] != 0]

        # 差分があれば表示
        if not diff_df.empty:
            st.subheader("📉 差分のあるデータ")
            st.dataframe(diff_df)

            # 差分グラフ表示
            st.subheader("📊 差分グラフ（理論消費量 vs 実消費量）")

            fig, ax = plt.subplots(figsize=(10, 4))
            ax.bar(
                diff_df["品目コード"],
                diff_df["理論消費量"],
                label="理論消費量",
                alpha=0.6,
            )
            ax.bar(
                diff_df["品目コード"], diff_df["実消費量"], label="実消費量", alpha=0.6
            )
            ax.set_ylabel("数量")
            ax.set_xlabel("品目コード")
            ax.set_title("理論 vs 実 消費量の比較")
            ax.legend()
            st.pyplot(fig)

            # 差分グラフをメモリに保存
            buf = io.BytesIO()
            fig.savefig(buf, format="png")
            buf.seek(0)

            # ダウンロードボタン
            st.download_button(
                label="📈 差分グラフをPNGでダウンロード",
                data=buf,
                file_name="inventory_diff_chart.png",
                mime="image/png",
            )

            # AIに「差が出た原因を仮説で説明して」と依頼するプロンプト
            ai_prompt = f"""
            以下の品目ごとに理論消費量と実消費量の差があります。
            その差について、どんな原因が考えられるか必ず日本語で要約してください。

            差分データ：
            {diff_df[["品目コード", "理論消費量", "実消費量", "差分"]].to_string(index=False)}
            """

            response = client.chat.completions.create(
                model="llama3-8b-8192",
                messages=[{"role": "user", "content": ai_prompt}],
                temperature=0.3,
            )

            ai_summary = response.choices[0].message.content
            st.subheader("🧠 AIによる差分要約")
            st.markdown(
                f"""
                <div style='background-color:#1e1e1e;padding:20px;border-radius:10px;margin-top:10px;color:#ffffff;'>
                {ai_summary}
                </div>
                """,
                unsafe_allow_html=True,
            )

            # AI要約テキストをUTF-8でエンコード
            analysis_text = ai_summary.encode("utf-8")

            st.download_button(
                label="🧠 AI分析結果をTXTでダウンロード",
                data=analysis_text,
                file_name="ai_analysis_result.txt",
                mime="text/plain",
            )

        else:
            st.success("✅ 差分はありませんでした")

    except Exception as e:
        st.error(f"❌ ファイル読み込みに失敗しました: {e}")
