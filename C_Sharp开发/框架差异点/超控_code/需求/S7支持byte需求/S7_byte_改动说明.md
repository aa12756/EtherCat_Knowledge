# 西门子 S7 支持 `plc_data_type: byte` — 改动说明

> 整理日期：2026-11-24  
> 改动仓库：**hardware_cc**（`main_cyy`）  
> 超控侧：**不在 super_ctl 做 byte→usint 映射**，依赖升级后的 **hw-cc**。

---

## 1. 背景与问题

| 现象 | 原因 |
|------|------|
| 设备/编排配置 `plc_data_type: "byte"`，S7 读失败 | `type_size` / `get_data` 无 `byte`，`type_size["byte"]` → KeyError |
| 读在 super_ctl 临时映射 `byte→usint` 后可读 | 底层 **usint** 已支持，缺的是 **byte 类型名** |
| PLC 调试「写入测试」报未知错误（改 hw-cc 前） | `write_data` 白名单仅 bool/int/real/string，`usint/byte` 进 `else` 抛 `RuntimeError` |
| 改 hw-cc 后仍偶发写失败 | 多为请求 **`output_value` 为空**（前端未传值），非 S7 协议问题 |
| Hsl 写 M100，超控读 DB1.0 为 0 | 地址区域不一致：超控 S7 走 **DB `db_read`**，不读 M 区 |

---

## 2. 方案选择

采用 **方案 A：在 hw-cc 中显式增加 `byte` 类型**（不映射为 `uint`，不与 `uint` 混用）。

- 西门子 **BYTE** = 单字节 0～255，与 **usint** 语义一致；**uint** 为 2 字节，禁止把 `byte` 映射到 `uint`。
- 实现上 `byte` 与 `usint` 共用 `snap7.util.get_usint` / `set_usint`。

---

## 3. 代码改动（hardware_cc）

**文件：** `packages/core/src/hw_cc/communication/protocol/s7.py`

### 3.1 `type_size`

- 新增：`"byte": 1`，注释说明与 usint 等价、前端常用名。

### 3.2 `get_data`

- 新增分支：`data_type == "byte"` → `snap7.util.get_usint(reading, 0)`。

### 3.3 `set_data`

- 新增分支：`data_type == "byte"` → `snap7.util.set_usint(reading, 0, int(data))`。

### 3.4 `write_data` 入参转换

在原有 `bool` / `int` / `real` / `string` 之后增加（**仅 `byte`**）：

```python
elif plc_data_type == "byte":
    output_value = int(output_value)
```

- **产品边界**：超控前端未开放 `usint` / `sint` 配置项；**写**仍仅对白名单类型开放。`usint` / `sint` 若经 API/JSON 传入，**写**会照旧进入 `else` 抛错（**读**在 hw-cc 层仍可实现，与历史行为一致）。

### 3.5 未改动的路径

- 仍通过 `db_num` + `starting_address` + `db_read` / `db_write`。
- `offset` 对 byte/usint 在 snap7 侧仍按缓冲区字节 0 读写；**DB 字节偏移由 `starting_address` 决定**（bool 的位偏移才重度依赖 `offset`）。

---

## 4. 超控（super_ctl）策略

| 项 | 说明 |
|----|------|
| 业务代码 | 已回退 `siemens_s7_compat.py` 及各处 `normalize_siemens_s7_plc_params` 接入 |
| 依赖 | 发布/联调需使用 **含本次改动的 hw-cc 版本**（或本地 editable 安装） |
| 接口 | 不变：`/api/v1/machine_resource/plc_read`、`plc_write`，`config.plc_data_type: "byte"` |

---

## 5. 本地联调

### 5.1 安装本地 hw-cc（super_ctl 的 .venv 无 `pip.exe`，用 uv）

```powershell
cd D:\EtherCat_Knowledge\C_Sharp开发\框架差异点\超控_code\hardware_cc\packages\core
uv pip install -e . --python "D:\EtherCat_Knowledge\C_Sharp开发\框架差异点\超控_code\super_ctl-main\.venv\Scripts\python.exe"
```

验证：

```powershell
& "...\super_ctl-main\.venv\Scripts\python.exe" -c "from hw_cc.communication.protocol import s7; print('byte' in s7.type_size, s7.__file__)"
```

应指向 `hardware_cc\packages\core\src\hw_cc\...`，且 `byte` 在 `type_size` 中。

### 5.2 Hsl 模拟器

- 地址用 **DB**：如 **`DB1.0`**，勿仅用 **M100** 与超控 DB 读对照。
- 与超控一致：`db_num: 1`，`starting_address: 0`，`rack/slot` 与 Hsl 一致。

### 5.3 PLC 调试页（HMI）

| 能力 | 说明 |
|------|------|
| **读 byte** | 已验证可行（实时数据 `data` 为数值） |
| **写 byte** | 左侧「写入值」对 **byte 无输入框**（仅 int/real/bool/string）；需在 **中间 JSON** 的 `config` 中填 **`"output_value": 88`** 再点写入测试 |
| **offset** | 变量 `db1_0` 建议 **`offset: 0`**，与 `starting_address: 0` 一致 |

写失败且日志为 `output_value: ""` → 属 **前端未传写入值**，非 hw-cc 能力问题。

### 5.4 重启后端

```powershell
Get-NetTCPConnection -LocalPort 18920 -ErrorAction SilentlyContinue |
  ForEach-Object { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue }

cd D:\EtherCat_Knowledge\C_Sharp开发\框架差异点\超控_code\super_ctl-main\backend\app
& "D:\EtherCat_Knowledge\C_Sharp开发\框架差异点\超控_code\super_ctl-main\.venv\Scripts\python.exe" .\run_local.py
```

---

## 6. 验收标准

1. Hsl **DB1.0** 写入 N → 超控 **读取测试**，`data === N`。
2. 超控 JSON **`output_value`** 写入 M → Hsl / 再读为 M。
3. 日志出现：`读取byte类型数据成功`、`往x：y写入数据:…成功`（类型名 **byte**，非必须显示 usint）。
4. 编排/设备管理中 `plc_data_type: byte` 的 S7 点读写与调试页行为一致（依赖 super_ctl 升级 hw-cc）。

---

## 7. 发版与后续

| 步骤 | 负责 |
|------|------|
| hardware_cc 提交、`main_cyy` 发新版（版本号高于 `1.0.3+20261120`） | hw-cc |
| super_ctl 更新 `hw-cc` 依赖并回归 byte 读写 | 超控 |
| PLC 调试页为 **byte** 增加左侧「写入值」输入（可选） | 前端/HMI |
| 变量模板中 byte 的 **offset** 默认 0（可选） | 配置/前端 |

---

## 8. 相关路径速查

| 内容 | 路径 |
|------|------|
| **数据块 / 起始位置 / 偏移量** | [S7_DB地址与偏移量说明.md](./S7_DB地址与偏移量说明.md) |
| S7 协议实现 | `hardware_cc/packages/core/src/hw_cc/communication/protocol/s7.py` |
| PLC 读写 API | `super_ctl-main/backend/app/app/api/api_v1/endpoints/machine_resources.py` |
| 本地启动 | `super_ctl-main/backend/app/run_local.py` |
| 前端 PLC 调试（打包） | `PlcProDebug`（如 `DeviceManagement/proDebugger`） |

---

## 9. 变更摘要（一句话）

在 **hw-cc S7** 中 **正式支持 `byte` 单字节读写**，并在 **`write_data` 仅为 `byte` 增加数值转换**；超控继续传 **`plc_data_type: "byte"`**，无需业务层映射。**`usint` / `sint` 写不在本需求范围内。**