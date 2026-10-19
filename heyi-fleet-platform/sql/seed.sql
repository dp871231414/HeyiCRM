-- 初始数据：全公司根节点、内置角色、管理员账号、车型字典
-- 管理员默认密码：123456（首次登录后请修改）

DELETE FROM sys_organization WHERE id = 1;
INSERT INTO sys_organization (id, name, type, parent_id, head, depth, sort_order, created_at, updated_at, deleted_at)
VALUES (1, '全公司', 'company', 0, NULL, 0, 0, NOW(), NOW(), 0);

DELETE FROM sys_role WHERE id IN (1,2,3,4);
INSERT INTO sys_role (id, name, description, scope, permissions, is_system, created_at, updated_at, deleted_at) VALUES
 (1, '系统管理员', '全公司数据可控、账号安全', 'all', '["dashboard.view","task.view","task.edit","market.view","market.edit","metric.view","metric.edit","sys.config.view","sys.config.edit","download.view"]', 1, NOW(), NOW(), 0),
 (2, '部门负责人', '本部门达成、缺口风险', 'dept_sub', '["dashboard.view","task.view","task.edit","market.view","market.edit","metric.view","sys.config.view","download.view"]', 1, NOW(), NOW(), 0),
 (3, '普通成员', '本人任务进度、是否临期', 'self', '["task.view","market.view","metric.view","sys.config.view","download.view"]', 1, NOW(), NOW(), 0),
 (4, '项目公司负责人', '本公司经营指标', 'dept_sub', '["dashboard.view","task.view","metric.view","metric.edit","sys.config.view","download.view"]', 1, NOW(), NOW(), 0);

-- 密码 123456 的 BCrypt 哈希（cost 10）
DELETE FROM sys_user WHERE account = 'admin';
INSERT INTO sys_user (id, name, account, password_hash, dept_id, role_id, scope, status, created_at, updated_at, deleted_at)
VALUES (1, '系统管理员', 'admin', '$2a$10$N.zmdr9k7uOCQb376NoUnuTJ8iAt6Z5EHsM8lE9lBOsl7iKTVKIUi', 1, 1, NULL, 'active', NOW(), NOW(), 0);

DELETE FROM sys_dict WHERE id IN (1,2);
INSERT INTO sys_dict (id, code, name, created_at, updated_at, deleted_at) VALUES
 (1, 'vehicle_model', '车辆型号', NOW(), NOW(), 0),
 (2, 'trailer_model', '挂车型号', NOW(), NOW(), 0);

INSERT INTO sys_dict_item (id, dict_id, value, sort, created_at, updated_at, deleted_at) VALUES
 (1, 1, '6*4牵引车', 0, NOW(), NOW(), 0),
 (2, 1, '4*2牵引车', 1, NOW(), NOW(), 0),
 (3, 1, '矿卡', 2, NOW(), NOW(), 0),
 (4, 1, '自卸车', 3, NOW(), NOW(), 0),
 (5, 2, '侧翻挂', 0, NOW(), NOW(), 0),
 (6, 2, '高栏挂', 1, NOW(), NOW(), 0),
 (7, 2, '后翻挂', 2, NOW(), NOW(), 0);
