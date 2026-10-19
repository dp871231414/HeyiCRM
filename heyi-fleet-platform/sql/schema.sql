-- 合一重卡生态经营看板 · MySQL 建表脚本
-- 说明：主键 BIGINT 由雪花算法生成（IdType.INPUT）；deleted_at 为逻辑删除字段（0 未删除，删除时写毫秒时间戳）。

CREATE TABLE IF NOT EXISTS sys_organization (
  id           BIGINT       NOT NULL COMMENT '主键',
  name         VARCHAR(64)  NOT NULL COMMENT '部门名称',
  type         VARCHAR(16)  NOT NULL DEFAULT 'dept' COMMENT 'company/dept/team/project',
  parent_id    BIGINT       NOT NULL DEFAULT 0 COMMENT '上级部门，0 表示根节点',
  head         VARCHAR(64)  DEFAULT NULL COMMENT '负责人姓名',
  depth        INT          DEFAULT 0 COMMENT '层级深度',
  sort_order   INT          DEFAULT 0 COMMENT '排序',
  created_by   VARCHAR(64)  DEFAULT NULL,
  updated_by   VARCHAR(64)  DEFAULT NULL,
  created_at   DATETIME     DEFAULT NULL,
  updated_at   DATETIME     DEFAULT NULL,
  deleted_at   BIGINT       NOT NULL DEFAULT 0 COMMENT '逻辑删除：0 未删除',
  PRIMARY KEY (id),
  KEY idx_parent (parent_id),
  KEY idx_deleted (deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='组织/部门';

CREATE TABLE IF NOT EXISTS sys_role (
  id           BIGINT       NOT NULL,
  name         VARCHAR(64)  NOT NULL COMMENT '角色名',
  description VARCHAR(255) DEFAULT NULL,
  scope        VARCHAR(16)  NOT NULL DEFAULT 'self' COMMENT 'self/dept/dept_sub/all',
  permissions TEXT         COMMENT 'JSON 数组字符串：菜单+按钮权限',
  is_system    TINYINT      NOT NULL DEFAULT 0 COMMENT '1=内置角色，受删除保护',
  created_by   VARCHAR(64)  DEFAULT NULL,
  updated_by   VARCHAR(64)  DEFAULT NULL,
  created_at   DATETIME     DEFAULT NULL,
  updated_at   DATETIME     DEFAULT NULL,
  deleted_at   BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_name_deleted (name, deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='角色';

CREATE TABLE IF NOT EXISTS sys_user (
  id            BIGINT       NOT NULL,
  name          VARCHAR(32)  NOT NULL COMMENT '姓名',
  account       VARCHAR(32)  NOT NULL COMMENT '登录账号',
  password_hash VARCHAR(128) NOT NULL COMMENT 'BCrypt 加盐哈希',
  dept_id       BIGINT       DEFAULT NULL COMMENT '所属部门',
  role_id       BIGINT       DEFAULT NULL COMMENT '角色',
  scope         VARCHAR(16)  DEFAULT NULL COMMENT '空=跟随角色默认范围',
  status        VARCHAR(16)  NOT NULL DEFAULT 'active' COMMENT 'active/disabled',
  last_login_at DATETIME     DEFAULT NULL,
  last_login_ip VARCHAR(64)  DEFAULT NULL,
  created_by    VARCHAR(64)  DEFAULT NULL,
  updated_by    VARCHAR(64)  DEFAULT NULL,
  created_at    DATETIME     DEFAULT NULL,
  updated_at    DATETIME     DEFAULT NULL,
  deleted_at    BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_account_deleted (account, deleted_at),
  KEY idx_dept (dept_id),
  KEY idx_role (role_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='账号';

CREATE TABLE IF NOT EXISTS sys_dict (
  id         BIGINT      NOT NULL,
  code       VARCHAR(64) DEFAULT NULL COMMENT '稳定编码，如 vehicle_model',
  name       VARCHAR(64) NOT NULL COMMENT '字典名称',
  created_by VARCHAR(64) DEFAULT NULL,
  updated_by VARCHAR(64) DEFAULT NULL,
  created_at DATETIME    DEFAULT NULL,
  updated_at DATETIME    DEFAULT NULL,
  deleted_at BIGINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='数据字典';

CREATE TABLE IF NOT EXISTS sys_dict_item (
  id         BIGINT       NOT NULL,
  dict_id    BIGINT       NOT NULL,
  value      VARCHAR(128) NOT NULL COMMENT '枚举值',
  sort       INT          NOT NULL DEFAULT 0,
  created_by VARCHAR(64)  DEFAULT NULL,
  updated_by VARCHAR(64)  DEFAULT NULL,
  created_at DATETIME     DEFAULT NULL,
  updated_at DATETIME     DEFAULT NULL,
  deleted_at BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_dict (dict_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='字典枚举值';

CREATE TABLE IF NOT EXISTS biz_task_group (
  id         BIGINT      NOT NULL,
  name       VARCHAR(25) NOT NULL COMMENT '任务组名，≤25 字',
  owner_id   BIGINT      DEFAULT NULL COMMENT '所属责任人（联合唯一）',
  owner_name VARCHAR(32) DEFAULT NULL,
  is_system  TINYINT     NOT NULL DEFAULT 0 COMMENT '1=内置「空」任务组，不可删',
  created_by VARCHAR(64) DEFAULT NULL,
  updated_by VARCHAR(64) DEFAULT NULL,
  created_at DATETIME    DEFAULT NULL,
  updated_at DATETIME    DEFAULT NULL,
  deleted_at BIGINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_name_owner (name, owner_id, deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务组';

CREATE TABLE IF NOT EXISTS biz_task (
  id            BIGINT        NOT NULL,
  name           VARCHAR(40)  NOT NULL COMMENT '任务名称',
  task_group_id  BIGINT       DEFAULT NULL,
  description    VARCHAR(150) DEFAULT NULL,
  abnormal       TINYINT      NOT NULL DEFAULT 0 COMMENT '是否异常（人工标记）',
  target         DECIMAL(18,2) NOT NULL COMMENT '目标，>0',
  done           DECIMAL(18,2) NOT NULL DEFAULT 0 COMMENT '已完成',
  unit           VARCHAR(16)  DEFAULT NULL,
  start_date     DATE         DEFAULT NULL,
  end_date       DATE         DEFAULT NULL,
  dept_id        BIGINT       DEFAULT NULL COMMENT '责任部门（由责任人自动带出）',
  owner_id       BIGINT       DEFAULT NULL,
  owner_name     VARCHAR(32)  DEFAULT NULL,
  progress       VARCHAR(500) DEFAULT NULL COMMENT '最新一条进展冗余快照',
  created_by     VARCHAR(64)  DEFAULT NULL,
  updated_by     VARCHAR(64)  DEFAULT NULL,
  created_at     DATETIME     DEFAULT NULL,
  updated_at     DATETIME     DEFAULT NULL,
  deleted_at     BIGINT       NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_group (task_group_id),
  KEY idx_owner (owner_id),
  KEY idx_dept (dept_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务';

CREATE TABLE IF NOT EXISTS biz_task_progress (
  id         BIGINT      NOT NULL,
  task_id    BIGINT      NOT NULL,
  content    VARCHAR(150) NOT NULL COMMENT '进展内容',
  created_by VARCHAR(64) DEFAULT NULL,
  updated_by VARCHAR(64) DEFAULT NULL,
  created_at DATETIME    DEFAULT NULL,
  updated_at DATETIME    DEFAULT NULL,
  deleted_at BIGINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_task (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务进展时间轴';

CREATE TABLE IF NOT EXISTS biz_market_project (
  id              BIGINT      NOT NULL,
  name            VARCHAR(40) NOT NULL,
  description     VARCHAR(150) DEFAULT NULL,
  stage           INT         NOT NULL DEFAULT 10 COMMENT '10/25/50/75/90/100',
  owner_id        BIGINT      DEFAULT NULL,
  owner_name      VARCHAR(32) DEFAULT NULL,
  owner_dept_id   BIGINT      DEFAULT NULL COMMENT '负责人所属部门',
  tractor_demand  INT         NOT NULL DEFAULT 0 COMMENT '车头需求汇总',
  trailer_demand  INT         NOT NULL DEFAULT 0 COMMENT '挂车需求汇总',
  progress        VARCHAR(500) DEFAULT NULL COMMENT '最新一条进展冗余快照',
  created_by      VARCHAR(64) DEFAULT NULL,
  updated_by      VARCHAR(64) DEFAULT NULL,
  created_at      DATETIME    DEFAULT NULL,
  updated_at      DATETIME    DEFAULT NULL,
  deleted_at      BIGINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_owner_dept (owner_dept_id),
  KEY idx_stage (stage)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='市场项目（商机）';

CREATE TABLE IF NOT EXISTS biz_project_requirement (
  id         BIGINT      NOT NULL,
  project_id BIGINT      NOT NULL,
  type       VARCHAR(16) NOT NULL COMMENT 'tractor/trailer',
  model      VARCHAR(64) DEFAULT NULL COMMENT '车型（取自字典）',
  battery    VARCHAR(32) DEFAULT NULL COMMENT '电池度数',
  qty        INT         NOT NULL DEFAULT 0,
  created_by VARCHAR(64) DEFAULT NULL,
  updated_by VARCHAR(64) DEFAULT NULL,
  created_at DATETIME    DEFAULT NULL,
  updated_at DATETIME    DEFAULT NULL,
  deleted_at BIGINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='车头/挂车需求明细行';

CREATE TABLE IF NOT EXISTS biz_project_progress (
  id         BIGINT      NOT NULL,
  project_id BIGINT      NOT NULL,
  content    VARCHAR(150) NOT NULL,
  created_by VARCHAR(64) DEFAULT NULL,
  updated_by VARCHAR(64) DEFAULT NULL,
  created_at DATETIME    DEFAULT NULL,
  updated_at DATETIME    DEFAULT NULL,
  deleted_at BIGINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_project (project_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='项目进展时间轴';

CREATE TABLE IF NOT EXISTS biz_metric_def (
  id           BIGINT      NOT NULL,
  code         VARCHAR(32) NOT NULL COMMENT '指标编码（稳定）',
  name         VARCHAR(64) NOT NULL,
  unit         VARCHAR(16) DEFAULT NULL,
  metric_group VARCHAR(16) NOT NULL COMMENT 'annual/project/monitor',
  family       VARCHAR(16) DEFAULT NULL,
  direction    VARCHAR(16) NOT NULL DEFAULT 'positive' COMMENT 'positive/negative',
  cycle        VARCHAR(16) NOT NULL DEFAULT 'month',
  weight       INT        NOT NULL DEFAULT 0,
  warn         DECIMAL(18,4) DEFAULT NULL,
  danger       DECIMAL(18,4) DEFAULT NULL,
  rate_target  DECIMAL(18,4) DEFAULT NULL,
  is_snapshot  TINYINT     NOT NULL DEFAULT 0,
  no_target    TINYINT     NOT NULL DEFAULT 0,
  owner_org_id BIGINT      DEFAULT NULL,
  created_by   VARCHAR(64) DEFAULT NULL,
  updated_by   VARCHAR(64) DEFAULT NULL,
  created_at   DATETIME    DEFAULT NULL,
  updated_at   DATETIME    DEFAULT NULL,
  deleted_at   BIGINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指标定义';

CREATE TABLE IF NOT EXISTS biz_metric_value (
  id         BIGINT      NOT NULL,
  metric_id  BIGINT      NOT NULL,
  org_id     BIGINT      DEFAULT NULL,
  period     VARCHAR(16) NOT NULL COMMENT '2026 或 2026-10',
  kind       VARCHAR(16) NOT NULL COMMENT 'target/actual',
  value      DECIMAL(18,4) DEFAULT NULL,
  created_by VARCHAR(64) DEFAULT NULL,
  updated_by VARCHAR(64) DEFAULT NULL,
  created_at DATETIME    DEFAULT NULL,
  updated_at DATETIME    DEFAULT NULL,
  deleted_at BIGINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_metric_org_period (metric_id, org_id, period, kind, deleted_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='指标目标值/实际值';

CREATE TABLE IF NOT EXISTS biz_download_record (
  id          BIGINT      NOT NULL,
  object_type VARCHAR(32) NOT NULL COMMENT 'task/market_project',
  filename    VARCHAR(128) NOT NULL,
  file_path   VARCHAR(255) DEFAULT NULL,
  created_by  VARCHAR(64) DEFAULT NULL,
  updated_by  VARCHAR(64) DEFAULT NULL,
  created_at  DATETIME    DEFAULT NULL,
  updated_at  DATETIME    DEFAULT NULL,
  deleted_at  BIGINT      NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  KEY idx_creator (created_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='下载中心导出记录';

CREATE TABLE IF NOT EXISTS sys_doc (
  id        BIGINT      NOT NULL,
  doc_key   VARCHAR(64) NOT NULL COMMENT '稳定键，如 usage',
  title     VARCHAR(128) DEFAULT NULL,
  doc_group VARCHAR(32) DEFAULT NULL COMMENT '文档分组（两级权限第二级）',
  content   LONGTEXT,
  version   INT         NOT NULL DEFAULT 1,
  created_by VARCHAR(64) DEFAULT NULL,
  updated_by VARCHAR(64) DEFAULT NULL,
  created_at DATETIME   DEFAULT NULL,
  updated_at DATETIME   DEFAULT NULL,
  deleted_at BIGINT     NOT NULL DEFAULT 0,
  PRIMARY KEY (id),
  UNIQUE KEY uk_doc_key (doc_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='文档中心';
