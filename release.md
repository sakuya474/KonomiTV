# KonomiTV リリース手順

このドキュメントでは、KonomiTV の新しいバージョンをリリースする手順を説明します。

## 概要

KonomiTV のリリースプロセスは、GitHub Actions を使用して自動化されています。以下の2つの主要なワークフローで構成されています：

1. **Create Release Commit** - リリースコミットの作成とバージョン番号の更新
2. **Publish Release** - ビルドとリリースの公開

## リリース手順

### ステップ 1: リリースコミットの作成

1. GitHub リポジトリの「Actions」タブを開く
2. 左側のメニューから「Create Release Commit」ワークフローを選択
3. 右上の「Run workflow」ボタンをクリック
4. 「Use workflow from」が `master` ブランチになっていることを確認
5. バージョン番号を入力（例: `0.3.4`）
   - **注意**: `v` プレフィックスは不要です（例: `v0.3.4` ではなく `0.3.4`）
6. 「Run workflow」ボタンをクリック

このワークフローは以下を自動的に実行します：

- 以下のファイルのバージョン番号を更新：
  - `client/package.json`
  - `installer/pyproject.toml`
  - `installer/KonomiTV-Installer.py`
  - `server/pyproject.toml`
  - `server/app/constants.py`
  - `Dockerfile`
  - `Readme.md`
- クライアントのビルド
- `master` ブランチに `Release: version X.X.X` というコミットメッセージでコミット
- `release` ブランチを更新

### ステップ 2: ビルドとリリースの自動実行

`release` ブランチが更新されると、「Publish Release」ワークフローが自動的に実行されます。

このワークフローは以下を実行します：

1. **インストーラーのビルド** (`build_installer` ジョブ)
   - Windows 用インストーラー (`KonomiTV-Installer.exe`)
   - Linux 用インストーラー (`KonomiTV-Installer.elf`)

2. **サードパーティーライブラリのビルド** (`build_thirdparty` ジョブ)
   - Windows 用ライブラリ (`thirdparty-windows.7z`)
   - Linux 用ライブラリ (`thirdparty-linux.tar.xz`)

3. **リリースの作成** (`publish_release` ジョブ)
   - ビルド成果物をダウンロード
   - バージョンタグ (`vX.X.X`) を作成
   - GitHub リリースを作成
   - ビルド成果物をリリースに添付

### ステップ 3: リリースの確認

1. GitHub Actions の「Actions」タブでワークフローの実行状況を確認
   - すべてのジョブが成功するまで待機（通常、30分〜1時間程度）
2. リリースページを確認: `https://github.com/sakuya474/KonomiTV/releases`
   - 新しいバージョンのリリースが作成されていることを確認
   - ビルド成果物が正しく添付されていることを確認

## トラブルシューティング

### リリースコミットが作成されない場合

- 「Create Release Commit」ワークフローの実行ログを確認
- `GIT_PUSH_TOKEN` シークレットが正しく設定されていることを確認
- `master` ブランチが最新であることを確認

### ビルドが失敗する場合

- 「Publish Release」ワークフローの実行ログを確認
- ビルドジョブ (`build_installer` または `build_thirdparty`) のエラーメッセージを確認
- 依存関係やビルド環境の問題がないか確認

### タグが既に存在する場合のエラー

既存のタグが存在する場合、タグ作成時にエラーが発生する可能性があります。

**解決方法:**

1. 既存のタグを削除：
   ```bash
   git tag -d v0.3.3
   git push origin :refs/tags/v0.3.3
   ```

2. `release` ブランチをリリースコミットにリセット：
   ```bash
   git checkout release
   git reset --hard <リリースコミットのハッシュ>
   git push origin release --force
   ```

3. または、ワークフローを手動で再実行：
   - GitHub Actions の「Publish Release」ワークフローを手動実行
   - 最新のコミットが `Release: version X.X.X` というメッセージになっていることを確認

### リリースが作成されない場合

- `release` ブランチの最新コミットが `Release: version X.X.X` というメッセージになっているか確認
- 「Publish Release」ワークフローが実行されているか確認
- ワークフローの実行条件 `if: contains(github.event.head_commit.message, 'Release:')` が満たされているか確認
- `publish_release` ジョブが実行されているか確認（`build_installer` と `build_thirdparty` が成功した後）

### リリースコミットの後に他のコミットが追加された場合

`release` ブランチの最新コミットが `Release: version X.X.X` でない場合、ワークフローがスキップされます。

**解決方法:**

1. `release` ブランチをリリースコミットにリセット：
   ```bash
   git checkout release
   git reset --hard <リリースコミットのハッシュ>
   git push origin release --force
   ```

2. または、ワークフローを手動で再実行：
   - GitHub Actions の「Publish Release」ワークフローを手動実行

## 重要な注意事項

1. **バージョン番号の形式**
   - セマンティックバージョニングに従うことを推奨: `MAJOR.MINOR.PATCH` (例: `0.3.4`)
   - `v` プレフィックスは不要（ワークフローが自動的に追加します）

2. **リリースコミットメッセージ**
   - コミットメッセージは必ず `Release: version X.X.X` という形式である必要があります
   - この形式でない場合、ワークフローがスキップされます

3. **ブランチの状態**
   - `release` ブランチは通常、リリース時にのみ更新されます
   - 手動で `release` ブランチを編集しないでください

4. **ワークフローの実行時間**
   - ビルドプロセスには時間がかかります（30分〜1時間程度）
   - すべてのジョブが完了するまで待機してください

5. **リリース前の確認**
   - リリース前に、変更内容を十分にテストしてください
   - `master` ブランチが安定した状態であることを確認してください

## 関連ワークフロー

- **Create Release Commit** (`.github/workflows/create_release_commit.yaml`)
  - リリースコミットの作成とバージョン番号の更新

- **Publish Release** (`.github/workflows/publish_release.yaml`)
  - ビルドとリリースの公開

- **Build Installer** (`.github/workflows/build_installer.yaml`)
  - インストーラーのビルド（`Publish Release` から呼び出される）

- **Build Thirdparty** (`.github/workflows/build_thirdparty.yaml`)
  - サードパーティーライブラリのビルド（`Publish Release` から呼び出される）

- **Publish Docker Image** (`.github/workflows/publish_docker_image.yaml`)
  - Docker イメージのビルドと公開（オプション、手動実行）

