package com.heyi.publics.common.cache;

import java.time.Duration;
import java.util.function.Supplier;

/**
 * 业务缓存。key 统一带前缀（技术方案约定前缀 lb），形如 {@code lb:dict:values:vehicle_model}。
 */
public interface CacheService {

    /** 拼装带前缀的 key：prefix:biz:part1:part2... */
    String key(String biz, Object... parts);

    /** 读取并反序列化；不存在返回 null。 */
    <T> T get(String key, Class<T> type);

    /** 读取；未命中时走 loader 并写回缓存。 */
    <T> T getOrLoad(String key, Class<T> type, Duration ttl, Supplier<T> loader);

    void set(String key, Object value, Duration ttl);

    void delete(String key);

    /** 删除某个业务域下的全部 key（按 prefix:biz:* 扫描，仅用于低频管理操作）。 */
    void deleteByBiz(String biz);
}
